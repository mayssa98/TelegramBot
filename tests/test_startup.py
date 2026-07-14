"""Smoke tests for application startup and the public health endpoint."""

from __future__ import annotations

from datetime import datetime

import database as db
from api.webhook import handler, health_payload, public_site_html
from bot import build_app


def test_public_health_payload():
    payload = health_payload()

    assert payload["ok"] is True
    assert payload["service"] == "TelegramBot webhook"
    assert payload["version"]
    datetime.fromisoformat(payload["timestamp"])


def test_webhook_handler_is_importable():
    assert handler.__name__ == "handler"


def test_public_site_links_to_bot():
    page = public_site_html()

    assert "<!doctype html>" in page.lower()
    assert "https://t.me/blackmarketa_bot" in page
    assert "?start=catalog" in page
    assert "?start=orders" in page
    assert "?start=support" in page


def test_bot_application_builds_with_mock_database(mock_mongodb, monkeypatch):
    monkeypatch.setattr(db, "init_db", lambda: None)

    application = build_app()

    assert application.bot.token

    command_names = {
        command
        for group in application.handlers.values()
        for registered in group
        for command in getattr(registered, "commands", ())
    }
    assert {
        "start",
        "catalog",
        "orders",
        "account",
        "support",
        "language",
        "affiliate",
        "terms",
        "privacy",
    } <= command_names
