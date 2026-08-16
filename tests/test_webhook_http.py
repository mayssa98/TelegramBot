"""HTTP-level smoke tests for the production webhook handler."""

from __future__ import annotations

import base64
import json
import threading
from contextlib import contextmanager
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from api.webhook import handler


@contextmanager
def running_server():
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_public_health_endpoint():
    with running_server() as base_url, urlopen(f"{base_url}/health", timeout=5) as response:
        payload = json.load(response)

    assert response.status == 200
    assert payload["ok"] is True
    assert payload["version"]
    assert payload["timestamp"]


def test_public_homepage_is_site():
    with running_server() as base_url, urlopen(f"{base_url}/", timeout=5) as response:
        body = response.read().decode()

    assert response.status == 200
    assert "text/html" in response.headers["Content-Type"]
    assert "https://t.me/blackmarketa_bot" in body


def test_admin_requires_authentication(monkeypatch):
    monkeypatch.setattr("api.webhook.DASHBOARD_PASSWORD", "secret")
    with running_server() as base_url:
        try:
            urlopen(f"{base_url}/admin", timeout=5)
        except HTTPError as exc:
            assert exc.code == 401
            assert exc.headers["WWW-Authenticate"]
        else:
            raise AssertionError("Admin dashboard was accessible without authentication")


def test_react_admin_requires_authentication(monkeypatch):
    monkeypatch.setattr("api.webhook.DASHBOARD_PASSWORD", "secret")
    with running_server() as base_url:
        try:
            urlopen(f"{base_url}/admin-v2", timeout=5)
        except HTTPError as exc:
            assert exc.code == 401
            assert exc.headers["WWW-Authenticate"] == 'Basic realm="TelegramBot Admin"'
        else:
            raise AssertionError("React admin dashboard was accessible without authentication")


def test_react_admin_serves_production_build(monkeypatch):
    monkeypatch.setattr("api.webhook.DASHBOARD_PASSWORD", "secret")
    encoded = base64.b64encode(b"admin:secret").decode()
    request = Request(
        "http://placeholder/admin-v2/orders",
        headers={"Authorization": f"Basic {encoded}"},
    )
    with running_server() as base_url:
        request.full_url = f"{base_url}/admin-v2/orders"
        with urlopen(request, timeout=5) as response:
            body = response.read().decode()

    assert response.status == 200
    assert "text/html" in response.headers["Content-Type"]
    assert '<div id="root"></div>' in body


def test_primary_admin_route_serves_react_build(monkeypatch):
    monkeypatch.setattr("api.webhook.DASHBOARD_PASSWORD", "secret")
    encoded = base64.b64encode(b"admin:secret").decode()
    request = Request(
        "http://placeholder/admin",
        headers={"Authorization": f"Basic {encoded}"},
    )
    with running_server() as base_url:
        request.full_url = f"{base_url}/admin"
        with urlopen(request, timeout=5) as response:
            body = response.read().decode()

    assert response.status == 200
    assert "BlackMarket Control Center" in body
    assert '<div id="root"></div>' in body


def test_react_admin_section_route_serves_spa(monkeypatch):
    monkeypatch.setattr("api.webhook.DASHBOARD_PASSWORD", "secret")
    encoded = base64.b64encode(b"admin:secret").decode()
    request = Request(
        "http://placeholder/admin/orders",
        headers={"Authorization": f"Basic {encoded}"},
    )
    with running_server() as base_url:
        request.full_url = f"{base_url}/admin/orders"
        with urlopen(request, timeout=5) as response:
            body = response.read().decode()

    assert response.status == 200
    assert '<div id="root"></div>' in body


def test_webhook_rejects_missing_secret(monkeypatch):
    monkeypatch.setenv("HP_WEBHOOK_SECRET", "expected-secret")
    request = Request(
        "http://placeholder/api/webhook",
        data=json.dumps({"update_id": 1}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with running_server() as base_url:
        request.full_url = f"{base_url}/api/webhook"
        try:
            urlopen(request, timeout=5)
        except HTTPError as exc:
            payload = json.load(exc)
            assert exc.code == 403
            assert payload["error"] == "invalid webhook secret"
        else:
            raise AssertionError("Webhook accepted a request without its secret")


def test_webhook_rejects_requests_when_secret_not_configured(monkeypatch):
    monkeypatch.delenv("HP_WEBHOOK_SECRET", raising=False)
    request = Request(
        "http://placeholder/api/webhook",
        data=json.dumps({"update_id": 1}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with running_server() as base_url:
        request.full_url = f"{base_url}/api/webhook"
        try:
            urlopen(request, timeout=5)
        except HTTPError as exc:
            payload = json.load(exc)
            assert exc.code == 503
            assert payload["error"] == "webhook_not_configured"
        else:
            raise AssertionError("Webhook accepted a request without a configured secret")


def test_webhook_requires_json_content_type(monkeypatch):
    monkeypatch.setenv("HP_WEBHOOK_SECRET", "expected-secret")
    request = Request(
        "http://placeholder/api/webhook",
        data=b"update_id=1",
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
        method="POST",
    )
    with running_server() as base_url:
        request.full_url = f"{base_url}/api/webhook"
        try:
            urlopen(request, timeout=5)
        except HTTPError as exc:
            assert exc.code == 415
        else:
            raise AssertionError("Webhook accepted a non-JSON request")
