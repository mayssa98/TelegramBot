"""Tests for admin-managed custom external API connectors."""

from __future__ import annotations

from cryptography.fernet import Fernet

import database as db
from app.domain import external_api_service


def _public_dns(*_args, **_kwargs):
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def test_connector_secret_is_encrypted_and_never_listed(mock_mongodb, monkeypatch):
    monkeypatch.setattr(external_api_service.socket, "getaddrinfo", _public_dns)
    monkeypatch.setattr(db, "_fernet", lambda: Fernet(Fernet.generate_key()))

    saved = external_api_service.save_connector({
        "name": "Supplier API",
        "endpoint": "https://api.example.com/v1/products",
        "method": "GET",
        "auth_type": "bearer",
        "secret": "super-secret-token",
        "headers": '{"Accept": "application/json"}',
    })

    stored = mock_mongodb.external_api_connectors.find_one({"id": saved["id"]})
    assert stored["encrypted_secret"] != "super-secret-token"
    assert "super-secret-token" not in str(external_api_service.list_connectors())
    assert saved["has_secret"] is True


def test_connector_rejects_private_or_insecure_endpoint(mock_mongodb, monkeypatch):
    monkeypatch.setattr(
        external_api_service.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )

    for endpoint in ("http://example.com/api", "https://localhost/api"):
        try:
            external_api_service.save_connector({
                "name": "Unsafe",
                "endpoint": endpoint,
                "method": "GET",
                "auth_type": "none",
            })
        except external_api_service.ExternalApiError:
            pass
        else:
            raise AssertionError(f"Unsafe endpoint accepted: {endpoint}")


def test_connector_can_execute_json_request(mock_mongodb, monkeypatch):
    cipher = Fernet(Fernet.generate_key())
    monkeypatch.setattr(external_api_service.socket, "getaddrinfo", _public_dns)
    monkeypatch.setattr(db, "_fernet", lambda: cipher)
    connector = external_api_service.save_connector({
        "name": "Order API",
        "endpoint": "https://api.example.com/v1/orders",
        "method": "POST",
        "auth_type": "api_key",
        "auth_header": "X-API-Key",
        "secret": "key-123",
        "body_template": '{"product_id": "A1"}',
    })
    captured = {}

    class FakeResponse:
        status = 201
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return b'{"order_id":"EXT-9"}'

    class FakeOpener:
        def open(self, request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()

    monkeypatch.setattr(external_api_service, "build_opener", lambda *_args: FakeOpener())
    result = external_api_service.execute(connector["id"])

    assert result["status"] == 201
    assert result["response"] == {"order_id": "EXT-9"}
    assert captured["request"].get_header("X-api-key") == "key-123"
    assert captured["timeout"] == 12
