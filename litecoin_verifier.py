"""Verify Litecoin deposits and obtain a live LTC/USDT conversion quote."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (
    LTC_BSC_RPC_URL,
    LTC_BSC_TOKEN_CONTRACT,
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


TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _rpc(method: str, params: list):
    request = Request(
        LTC_BSC_RPC_URL,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "BlackMarketBot/1.0 ltc-bsc-verifier"},
    )
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError(payload["error"].get("message") or "BSC RPC error")
    return payload.get("result")


def _hex_int(value) -> int:
    return int(str(value or "0x0"), 16)


def verify_litecoin_deposit(
    txid: str,
    destination: str,
    created_at: int | None = None,
) -> dict:
    """Verify a confirmed LTC transaction and derive the amount sent to our address."""
    txid = str(txid or "").strip().lower()
    destination = str(destination or "").strip()
    if not re.fullmatch(r"0x[a-f0-9]{64}", txid):
        return _result("failed", "invalid_format", "Invalid BSC transaction hash.")
    if not re.fullmatch(r"0x[a-fA-F0-9]{40}", destination):
        return _result("failed", "not_configured", "Litecoin receiving address is not configured.")

    try:
        receipt = _rpc("eth_getTransactionReceipt", [txid])
        if receipt is None:
            return _result("pending", "not_mined", "BSC transaction is not mined yet.")
        if _hex_int(receipt.get("status")) != 1:
            return _result("failed", "transaction_failed", "The BSC transaction failed on-chain.")
        block_number = _hex_int(receipt.get("blockNumber"))
        latest_block = _hex_int(_rpc("eth_blockNumber", []))
        confirmations = max(0, latest_block - block_number + 1)
        if confirmations < LTC_MIN_CONFIRMATIONS:
            return _result(
                "pending", "confirming", "Waiting for Litecoin confirmations.",
                confirmations=confirmations,
            )

        satoshis = 0
        destination_topic = destination.lower().replace("0x", "").rjust(64, "0")
        contract = LTC_BSC_TOKEN_CONTRACT.lower()
        for log in receipt.get("logs") or []:
            topics = [str(topic).lower() for topic in (log.get("topics") or [])]
            if str(log.get("address") or "").lower() != contract or len(topics) < 3:
                continue
            if topics[0] == TRANSFER_TOPIC and topics[2].endswith(destination_topic):
                satoshis += _hex_int(log.get("data"))
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
            txid=txid, network="bsc", token_contract=LTC_BSC_TOKEN_CONTRACT,
            ltc_amount=float(amount),
            confirmations=confirmations,
            received_at=None,
        )
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return _result("pending", "api_unavailable", f"BSC RPC unavailable: {exc}")


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
