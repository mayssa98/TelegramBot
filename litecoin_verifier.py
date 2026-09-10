"""Verify Litecoin deposits and obtain a live LTC/USDT conversion quote."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (
    LTC_BLOCKCYPHER_API_BASE,
    LTC_MIN_CONFIRMATIONS,
    LTC_MIN_DEPOSIT,
    LTC_PRICE_API_URL,
)

SATOSHIS_PER_LTC = Decimal("100000000")


def _result(status: str, code: str, reason: str, **values):
    return {"status": status, "code": code, "reason": reason, **values}


def _request_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "BlackMarketBot/1.0 litecoin-verifier",
        },
    )
    with urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _unix_time(value) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC).timestamp())
    except (ValueError, TypeError):
        return None


def verify_litecoin_deposit(
    txid: str,
    destination: str,
    created_at: int | None = None,
) -> dict:
    """Verify a confirmed LTC transaction and derive the amount sent to our address."""
    txid = str(txid or "").strip().lower()
    destination = str(destination or "").strip()
    if not re.fullmatch(r"[a-f0-9]{64}", txid):
        return _result("failed", "invalid_format", "Invalid Litecoin transaction ID.")
    if not destination:
        return _result("failed", "not_configured", "Litecoin receiving address is not configured.")

    try:
        payload = _request_json(f"{LTC_BLOCKCYPHER_API_BASE}/txs/{txid}")
        if payload.get("error"):
            return _result("failed", "not_found", "Litecoin transaction was not found.")
        if payload.get("double_spend"):
            return _result("failed", "double_spend", "The Litecoin transaction is a double spend.")

        confirmations = max(0, int(payload.get("confirmations") or 0))
        if confirmations < LTC_MIN_CONFIRMATIONS:
            return _result(
                "pending", "confirming", "Waiting for Litecoin confirmations.",
                confirmations=confirmations,
            )

        received_at = _unix_time(payload.get("received") or payload.get("confirmed"))
        if created_at and received_at and received_at < int(created_at) - 600:
            return _result(
                "failed", "transaction_too_old",
                "The Litecoin transaction predates this deposit request.",
            )

        satoshis = 0
        for output in payload.get("outputs") or []:
            addresses = [str(value).strip() for value in (output.get("addresses") or [])]
            if destination in addresses:
                satoshis += int(output.get("value") or 0)
        amount = Decimal(satoshis) / SATOSHIS_PER_LTC
        minimum = Decimal(str(LTC_MIN_DEPOSIT))
        if amount <= 0:
            return _result("failed", "wrong_recipient", "LTC was not sent to the configured address.")
        if amount < minimum:
            return _result(
                "failed", "minimum", f"Minimum Litecoin deposit is {minimum} LTC.",
                ltc_amount=float(amount),
            )
        return _result(
            "confirmed", "confirmed", "Litecoin deposit confirmed.",
            txid=txid,
            ltc_amount=float(amount),
            confirmations=confirmations,
            received_at=received_at,
        )
    except HTTPError as exc:
        if exc.code == 404:
            return _result("failed", "not_found", "Litecoin transaction was not found.")
        return _result("pending", "api_unavailable", f"Litecoin API unavailable: HTTP {exc.code}")
    except (URLError, TimeoutError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return _result("pending", "api_unavailable", f"Litecoin API unavailable: {exc}")


def fetch_ltc_usdt_quote() -> dict:
    """Return the live LTC/USDT price used for an internal-wallet credit."""
    try:
        payload = _request_json(LTC_PRICE_API_URL)
        price = Decimal(str(payload.get("price") or "0"))
        if not price.is_finite() or price <= 0:
            raise InvalidOperation("invalid LTC price")
        return _result(
            "confirmed", "confirmed", "LTC/USDT quote received.",
            price=float(price), source="binance_ltcusdt",
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, InvalidOperation, json.JSONDecodeError) as exc:
        return _result("pending", "quote_unavailable", f"LTC/USDT quote unavailable: {exc}")
