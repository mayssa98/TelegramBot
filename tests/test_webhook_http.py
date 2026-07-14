"""HTTP-level smoke tests for the Vercel webhook handler."""

from __future__ import annotations

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


def test_webhook_allows_missing_secret_when_not_configured(monkeypatch):
    monkeypatch.delenv("HP_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr("api.webhook.db.claim_update", lambda update_id: False)
    request = Request(
        "http://placeholder/api/webhook",
        data=json.dumps({"update_id": 1}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with running_server() as base_url:
        request.full_url = f"{base_url}/api/webhook"
        with urlopen(request, timeout=5) as response:
            payload = json.load(response)

    assert response.status == 200
    assert payload["ok"] is True
