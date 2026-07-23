"""Regression tests for Binance Pay transaction matching."""

from __future__ import annotations

import payment_verifier


def test_txid_verification_matches_exact_amount_without_memo(monkeypatch):
    monkeypatch.setattr(payment_verifier, "BINANCE_API_KEY", "key")
    monkeypatch.setattr(payment_verifier, "BINANCE_API_SECRET", "secret")
    monkeypatch.setattr(payment_verifier, "_fetch_pay_transactions", lambda _start: [{
        "transactionId": "BINANCE_TX_123",
        "amount": "5.00000000",
        "currency": "USDT",
    }])

    result = payment_verifier.verify_payment(
        "BINANCE_TX_123", 5, "USDT", created_at=100
    )

    assert result["status"] == "confirmed"


def test_automatic_verification_matches_amount_and_memo(monkeypatch):
    monkeypatch.setattr(payment_verifier, "BINANCE_API_KEY", "key")
    monkeypatch.setattr(payment_verifier, "BINANCE_API_SECRET", "secret")
    monkeypatch.setattr(payment_verifier, "_fetch_pay_transactions", lambda _start: [
        {
            "transactionId": "WRONG_MEMO_TX",
            "transactionTime": 101_000,
            "amount": "5.00",
            "currency": "USDT",
            "remark": "999",
        },
        {
            "transactionId": "RIGHT_MEMO_TX",
            "transactionTime": 102_000,
            "amount": "5.00",
            "currency": "USDT",
            "remark": "123",
        },
    ])

    result = payment_verifier.verify_payment_by_amount(
        5, "USDT", created_at=100, expected_memo=123
    )

    assert result["status"] == "confirmed"
    assert result["txid"] == "RIGHT_MEMO_TX"
