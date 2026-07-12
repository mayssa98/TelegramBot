"""Smoke tests for application startup and the public health endpoint."""

from __future__ import annotations

from datetime import datetime

import database as db
from api.webhook import handler, health_payload
from bot import build_app


def test_public_health_payload():
    payload = health_payload()

    assert payload["ok"] is True
    assert payload["service"] == "TelegramBot webhook"
    assert payload["version"]
    datetime.fromisoformat(payload["timestamp"])


def test_webhook_handler_is_importable():
    assert handler.__name__ == "handler"


def test_bot_application_builds_with_mock_database(mock_mongodb, monkeypatch):
    monkeypatch.setattr(db, "init_db", lambda: None)

    application = build_app()

    assert application.bot.token
