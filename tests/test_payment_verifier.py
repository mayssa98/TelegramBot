"""Regression tests for Binance Pay transaction matching."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import payment_verifier


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


def test_binance_endpoint_fallback_after_http_451(monkeypatch):
    monkeypatch.setattr(payment_verifier, "BINANCE_API_KEY", "key")
    monkeypatch.setattr(payment_verifier, "BINANCE_API_SECRET", "secret")
    monkeypatch.setattr(
        payment_verifier,
        "BINANCE_API_BASES",
        ("https://blocked.example", "https://working.example"),
    )
    requested_hosts = []

    def fake_urlopen(request, timeout):
        requested_hosts.append(request.full_url.split("/", 3)[2])
        if "blocked.example" in request.full_url:
            raise HTTPError(request.full_url, 451, "Unavailable", {}, io.BytesIO())
        return _FakeResponse({"success": True, "code": "000000", "data": []})

    monkeypatch.setattr(payment_verifier, "urlopen", fake_urlopen)

    assert payment_verifier._fetch_pay_transactions(0) == []
    assert requested_hosts == ["blocked.example", "working.example"]


def test_binance_healthcheck_does_not_expose_credentials(monkeypatch):
    monkeypatch.setattr(payment_verifier, "BINANCE_API_KEY", "super-secret-key")
    monkeypatch.setattr(payment_verifier, "BINANCE_API_SECRET", "super-secret-value")
    monkeypatch.setattr(
        payment_verifier,
        "_fetch_pay_transactions_with_base",
        lambda _start: ([{"transactionId": "tx"}], "https://api1.binance.com"),
    )

    result = payment_verifier.binance_healthcheck()

    assert result["ok"] is True
    assert result["transactions_24h"] == 1
    assert "super-secret" not in json.dumps(result)


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


def test_txid_verification_accepts_order_id_shown_on_binance_receipt(monkeypatch):
    monkeypatch.setattr(payment_verifier, "BINANCE_API_KEY", "key")
    monkeypatch.setattr(payment_verifier, "BINANCE_API_SECRET", "secret")
    monkeypatch.setattr(payment_verifier, "_fetch_pay_transactions", lambda _start: [{
        "transactionId": "INTERNAL_PAY_TX_123",
        "orderId": "444629486564122624",
        "amount": "5",
        "currency": "USDT",
    }])

    result = payment_verifier.verify_payment(
        "444629486564122624", 5, "USDT", created_at=100
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
