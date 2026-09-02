"""Read-only verification of finalized USDT transfers on EVM networks."""

from __future__ import annotations

import json
import re
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (
    ONCHAIN_BSC_RPC_URL,
    ONCHAIN_POLL_INTERVAL,
    ONCHAIN_POLYGON_RPC_URL,
    ONCHAIN_VERIFY_TIMEOUT,
    USDT_BSC_CONTRACT,
    USDT_POLYGON_CONTRACT,
)

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
NETWORKS = {
    "bsc": {
        "name": "BSC (BEP20)", "chain_id": 56, "rpc_url": ONCHAIN_BSC_RPC_URL,
        "contract": USDT_BSC_CONTRACT, "decimals": 18, "confirmations": 2,
    },
    "polygon": {
        "name": "Polygon", "chain_id": 137, "rpc_url": ONCHAIN_POLYGON_RPC_URL,
        "contract": USDT_POLYGON_CONTRACT, "decimals": 6, "confirmations": 3,
    },
}


def _rpc(network: str, method: str, params: list):
    settings = NETWORKS[network]
    request = Request(
        settings["rpc_url"],
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "BlackMarketBot/1.0 onchain-verifier",
        },
    )
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError(payload["error"].get("message") or "Blockchain RPC error")
    return payload.get("result")


def _hex_int(value) -> int:
    if isinstance(value, int):
        return value
    return int(str(value or "0x0"), 16)


def _result(status: str, code: str, reason: str, **values):
    return {"status": status, "code": code, "reason": reason, **values}


def verify_onchain_usdt_once(
    txid: str,
    network: str,
    amount,
    destination: str,
    created_at: int | None = None,
):
    """Validate one finalized ERC-20 USDT transfer from its transaction receipt."""
    txid = str(txid or "").strip().lower()
    network = str(network or "").strip().lower()
    destination = str(destination or "").strip().lower()
    if network not in NETWORKS:
        return _result("failed", "invalid_network", "Unsupported blockchain network.")
    if not re.fullmatch(r"0x[a-f0-9]{64}", txid):
        return _result("failed", "invalid_format", "Invalid blockchain transaction hash.")
    if not re.fullmatch(r"0x[a-f0-9]{40}", destination):
        return _result("failed", "not_configured", "Receiving wallet address is invalid.")

    settings = NETWORKS[network]
    contract = str(settings["contract"]).lower()
    if not re.fullmatch(r"0x[a-f0-9]{40}", contract):
        return _result("failed", "not_configured", "USDT contract is not configured.")
    try:
        expected_decimal = Decimal(str(amount)) * (Decimal(10) ** settings["decimals"])
        if expected_decimal != expected_decimal.to_integral_value() or expected_decimal <= 0:
            return _result("failed", "invalid_amount", "Invalid expected USDT amount.")
        expected_units = int(expected_decimal)

        chain_id = _hex_int(_rpc(network, "eth_chainId", []))
        if chain_id != settings["chain_id"]:
            return _result("failed", "wrong_network", "RPC endpoint returned the wrong network.")
        receipt = _rpc(network, "eth_getTransactionReceipt", [txid])
        if receipt is None:
            return _result("pending", "not_mined", "Transaction is not mined yet.")
        if _hex_int(receipt.get("status")) != 1:
            return _result("failed", "transaction_failed", "Transaction failed on-chain.")

        transfer_logs = []
        recipient_logs = []
        for log in receipt.get("logs") or []:
            topics = [str(topic).lower() for topic in (log.get("topics") or [])]
            if str(log.get("address") or "").lower() != contract:
                continue
            if len(topics) < 3 or topics[0] != TRANSFER_TOPIC:
                continue
            transfer_logs.append(log)
            recipient = "0x" + topics[2][-40:]
            if recipient == destination:
                recipient_logs.append(log)
                if _hex_int(log.get("data")) == expected_units:
                    block_number = _hex_int(receipt.get("blockNumber"))
                    latest_block = _hex_int(_rpc(network, "eth_blockNumber", []))
                    confirmations = latest_block - block_number + 1
                    if confirmations < settings["confirmations"]:
                        return _result(
                            "pending", "confirming", "Waiting for blockchain confirmations.",
                            confirmations=confirmations,
                        )
                    if created_at:
                        block = _rpc(network, "eth_getBlockByNumber", [hex(block_number), False])
                        block_time = _hex_int((block or {}).get("timestamp"))
                        if block_time and block_time < int(created_at) - 600:
                            return _result("failed", "transaction_too_old", "Transaction predates this order.")
                    return _result(
                        "confirmed", "confirmed", "USDT transfer confirmed on-chain.",
                        network=settings["name"], confirmations=confirmations,
                        amount=float(Decimal(expected_units) / (Decimal(10) ** settings["decimals"])),
                    )
        if not transfer_logs:
            return _result("failed", "wrong_token", "No transfer from the configured USDT contract was found.")
        if not recipient_logs:
            return _result("failed", "wrong_recipient", "USDT was not sent to the configured wallet.")
        return _result("failed", "wrong_amount", "The transferred USDT amount does not match.")
    except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, InvalidOperation) as exc:
        return _result("pending", "rpc_unavailable", f"Blockchain RPC unavailable: {exc}")


def verify_onchain_usdt(
    txid: str,
    network: str,
    amount,
    destination: str,
    created_at: int | None = None,
    *,
    timeout_seconds: float | None = None,
    poll_interval: float | None = None,
):
    """Poll until the transfer confirms, fails validation, or reaches its timeout."""
    timeout = ONCHAIN_VERIFY_TIMEOUT if timeout_seconds is None else max(0, timeout_seconds)
    interval = ONCHAIN_POLL_INTERVAL if poll_interval is None else max(0, poll_interval)
    deadline = time.monotonic() + timeout
    while True:
        result = verify_onchain_usdt_once(txid, network, amount, destination, created_at)
        if result["status"] != "pending" or time.monotonic() >= deadline:
            return result
        time.sleep(interval)
