"""Tests for the all-in-one Railway process."""

from __future__ import annotations

import config
import railway_server


def test_deployment_requires_a_generated_railway_domain(monkeypatch):
    monkeypatch.setattr(config, "configuration_issues", lambda **_kwargs: [])
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "production-id")
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    monkeypatch.delenv("HP_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("HP_WEBHOOK_SECRET", "w" * 32)
    monkeypatch.setenv("CRON_SECRET", "a" * 32)

    assert "Railway public domain (generate one under Networking)" in (
        railway_server.deployment_issues()
    )


def test_deployment_accepts_railway_generated_domain(monkeypatch):
    monkeypatch.setattr(config, "configuration_issues", lambda **_kwargs: [])
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "production-id")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "blackmarket.up.railway.app")
    monkeypatch.delenv("HP_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("HP_WEBHOOK_SECRET", "w" * 32)
    monkeypatch.setenv("CRON_SECRET", "a" * 32)

    assert railway_server.deployment_issues() == []


def test_webhook_registration_retries_transient_failure(monkeypatch):
    results = iter(
        [
            {"ok": False, "message": "temporary"},
            {"ok": True, "url": "https://blackmarket.up.railway.app/api/webhook"},
        ]
    )
    monkeypatch.setattr(
        railway_server.webhook,
        "repair_telegram_webhook",
        lambda: next(results),
    )

    result = railway_server.register_telegram_webhook(attempts=2, retry_seconds=0)

    assert result["ok"] is True
