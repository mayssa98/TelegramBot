"""Telegram notifications sent after manual wallet credits."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from api import webhook


class FakeBot:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.messages = []

    async def send_message(self, **kwargs):
        if self.fail:
            raise RuntimeError("Telegram unavailable")
        self.messages.append(kwargs)


def test_manual_wallet_credit_notifies_customer(monkeypatch):
    bot = FakeBot()
    monkeypatch.setattr(webhook, "_application", lambda: SimpleNamespace(bot=bot))
    monkeypatch.setattr(webhook, "_run_async", asyncio.run)

    sent = webhook._notify_wallet_adjustment(
        {"user_id": 42, "amount": 12.5, "balance": 30.75},
        "Bonus fidélité",
    )

    assert sent is True
    assert bot.messages[0]["chat_id"] == 42
    assert "+12.50" in bot.messages[0]["text"]
    assert "30.75" in bot.messages[0]["text"]
    assert "Bonus fidélité" in bot.messages[0]["text"]


def test_wallet_credit_remains_successful_when_notification_fails(monkeypatch):
    bot = FakeBot(fail=True)
    monkeypatch.setattr(webhook, "_application", lambda: SimpleNamespace(bot=bot))
    monkeypatch.setattr(webhook, "_run_async", asyncio.run)

    assert webhook._notify_wallet_adjustment(
        {"user_id": 42, "amount": 5, "balance": 5},
    ) is False


def test_manual_debit_does_not_send_credit_notification(monkeypatch):
    bot = FakeBot()
    monkeypatch.setattr(webhook, "_application", lambda: SimpleNamespace(bot=bot))
    monkeypatch.setattr(webhook, "_run_async", asyncio.run)

    assert webhook._notify_wallet_adjustment(
        {"user_id": 42, "amount": -2, "balance": 3},
    ) is False
    assert bot.messages == []


def test_onchain_approval_notifies_customer(monkeypatch, mock_mongodb):
    bot = FakeBot()
    mock_mongodb.users.insert_one({"telegram_id": 42, "lang": "en"})
    monkeypatch.setattr(webhook, "_application", lambda: SimpleNamespace(bot=bot))
    monkeypatch.setattr(webhook, "_run_async", asyncio.run)

    sent = webhook._notify_onchain_topup(
        {"user_id": 42, "amount_cents": 900, "balance": 15},
        approved=True,
    )

    assert sent is True
    assert bot.messages[0]["chat_id"] == 42
    assert "9.00" in bot.messages[0]["text"]
    assert "15.00" in bot.messages[0]["text"]
