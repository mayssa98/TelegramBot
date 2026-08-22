import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from app.domain import admin_ai_service as service
from config import normalized_http_url


def dashboard_data():
    return {
        "summary": {"orders": 9, "revenue_today": 12.5},
        "alerts": [{"type": "stock_low", "message": "Stock faible", "severity": "warning"}],
        "services": [{
            "id": 1,
            "name": "Canva",
            "active": 1,
            "offers": [{
                "id": 11,
                "name": "Canva 1m",
                "price": 2,
                "stock": 3,
                "active": 1,
                "delivery": ["secret-account"],
                "api_key": "secret-key",
            }],
        }],
        "orders": [{
            "id": 21,
            "status": "paid",
            "offer_name": "Canva 1m",
            "user_id": 999,
            "delivery": ["secret-delivery"],
        }],
        "tickets": [{"id": 31, "status": "waiting_admin", "message": "private text"}],
        "users": [{"telegram_id": 41, "username": "private_user", "banned": False}],
        "dashboard_write_token": "never-send-this",
    }


def test_safe_snapshot_excludes_secrets_and_customer_content():
    snapshot = service.safe_dashboard_snapshot(dashboard_data())
    encoded = json.dumps(snapshot)

    assert "secret-account" not in encoded
    assert "secret-delivery" not in encoded
    assert "secret-key" not in encoded
    assert "private text" not in encoded
    assert "private_user" not in encoded
    assert "never-send-this" not in encoded
    assert snapshot["services"][0]["offers"][0]["id"] == 11


def test_sanitize_actions_allows_only_known_entities_and_actions():
    snapshot = service.safe_dashboard_snapshot(dashboard_data())
    actions = service.sanitize_actions([
        {"action": "toggle_offer", "label": "Désactiver", "parameters": {"offer_id": 11}},
        {"action": "toggle_offer", "parameters": {"offer_id": 999}},
        {"action": "reveal_inventory", "parameters": {"inventory_id": 1}},
        {"action": "toggle_ban", "parameters": {"user_id": 41, "banned": True}},
    ], snapshot)

    assert [item["action"] for item in actions] == ["toggle_offer", "toggle_ban"]
    assert actions[1]["parameters"]["banned"] == 1


def test_chat_rejects_model_outside_configured_list(monkeypatch):
    monkeypatch.setattr(service, "AI_COMPARISON_MODELS", ("allowed-model",))

    with pytest.raises(service.AdminAIError, match="Modèle non autorisé"):
        service.chat([{"role": "user", "content": "Résumé"}], "other-model", dashboard_data())


def test_markdown_url_copied_from_chat_is_repaired():
    assert normalized_http_url(
        "[https://co.agentrouter.org/v1/chat/completions](https://agentrouter.org/v1/chat/completions)"
    ) == "https://agentrouter.org/v1/chat/completions"


def test_agentrouter_unauthorized_client_error_is_explicit():
    body = BytesIO(json.dumps({
        "error": {"message": "unauthorized client detected, contact support"}
    }).encode())
    error = HTTPError("https://agentrouter.org", 401, "Unauthorized", {}, body)

    message = service._provider_error_message(error)

    assert "unauthorized client" in message
    assert "Railway" in message


def test_chat_returns_sanitized_suggestions(monkeypatch):
    monkeypatch.setattr(service, "AI_COMPARISON_API_URL", "https://ai.example/v1/chat/completions")
    monkeypatch.setattr(service, "AI_COMPARISON_API_KEY", "test-token")
    monkeypatch.setattr(service, "AI_COMPARISON_MODELS", ("model-a",))
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            result = {
                "reply": "Le stock de Canva est faible.",
                "suggested_actions": [
                    {"action": "toggle_offer", "label": "Désactiver Canva", "parameters": {"offer_id": 11}},
                    {"action": "delete_everything", "parameters": {}},
                ],
            }
            return json.dumps({"choices": [{"message": {"content": json.dumps(result)}}]}).encode()

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr(service, "urlopen", fake_urlopen)
    result = service.chat([{"role": "user", "content": "Analyse le stock"}], "model-a", dashboard_data())

    assert result["reply"] == "Le stock de Canva est faible."
    assert [item["action"] for item in result["suggested_actions"]] == ["toggle_offer"]
    sent = json.dumps(captured["body"])
    assert "secret-delivery" not in sent
    assert "never-send-this" not in sent
