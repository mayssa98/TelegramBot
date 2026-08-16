"""Fetch and mask Binance crypto withdrawal history for workbook export."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import BINANCE_API_BASES, BINANCE_API_KEY, BINANCE_API_SECRET

OUTPUT = Path(__file__).with_name("withdrawals_masked.json")
START = datetime(2017, 7, 1, tzinfo=UTC)
WINDOW = timedelta(days=89)
STATUS = {
    0: "Email sent",
    1: "Cancelled",
    2: "Awaiting approval",
    3: "Rejected",
    4: "Processing",
    5: "Failed",
    6: "Completed",
}


def mask(value: object, left: int = 8, right: int = 6) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= left + right + 3:
        return text[:3] + "…" + text[-2:]
    return text[:left] + "…" + text[-right:]


def mask_info(value: object) -> str:
    """Preserve short status messages while masking identifier-like payloads."""
    text = str(value or "").strip()
    if len(text) > 40 or re.fullmatch(r"(?:0x)?[0-9a-fA-F,]+", text):
        return mask(text, 10, 8)
    return text


def signed_request(base_url: str, params: dict[str, object]) -> list[dict]:
    query = urlencode({**params, "recvWindow": 10000, "timestamp": int(time.time() * 1000)})
    signature = hmac.new(
        BINANCE_API_SECRET.encode(), query.encode(), hashlib.sha256
    ).hexdigest()
    request = Request(
        f"{base_url}/sapi/v1/capital/withdraw/history?{query}&signature={signature}",
        headers={"X-MBX-APIKEY": BINANCE_API_KEY, "Accept": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode())
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected Binance response")
    return payload


def fetch_page(params: dict[str, object]) -> list[dict]:
    failures: list[str] = []
    for base_url in BINANCE_API_BASES:
        try:
            return signed_request(base_url, params)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:500]
            failures.append(f"{base_url}: HTTP {exc.code} {body}")
            if exc.code not in {403, 451, 502, 503, 504}:
                break
        except (URLError, TimeoutError) as exc:
            failures.append(f"{base_url}: {type(exc).__name__}")
    raise RuntimeError(" | ".join(failures))


def main() -> None:
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        raise RuntimeError("Binance API credentials are not configured")
    rows: list[dict] = []
    cursor = START
    end_all = datetime.now(UTC)
    request_count = 0
    while cursor < end_all:
        window_end = min(cursor + WINDOW, end_all)
        offset = 0
        while True:
            batch = fetch_page({
                "startTime": int(cursor.timestamp() * 1000),
                "endTime": int(window_end.timestamp() * 1000),
                "offset": offset,
                "limit": 1000,
            })
            request_count += 1
            rows.extend(batch)
            if len(batch) < 1000:
                break
            offset += len(batch)
            time.sleep(0.15)
        cursor = window_end + timedelta(milliseconds=1)
        time.sleep(0.15)

    unique: dict[str, dict] = {}
    for row in rows:
        key = str(row.get("id") or "|").strip() or "|".join(
            str(row.get(field) or "") for field in ("txId", "applyTime", "coin", "amount")
        )
        unique[key] = row

    cleaned = []
    for row in unique.values():
        status_code = int(row.get("status", -1))
        cleaned.append({
            "apply_time": str(row.get("applyTime") or ""),
            "complete_time": str(row.get("completeTime") or ""),
            "coin": str(row.get("coin") or ""),
            "amount": float(row.get("amount") or 0),
            "fee": float(row.get("transactionFee") or 0),
            "network": str(row.get("network") or ""),
            "status": STATUS.get(status_code, f"Unknown ({status_code})"),
            "transfer_type": "Internal" if int(row.get("transferType") or 0) == 1 else "External",
            "wallet": "Funding" if int(row.get("walletType") or 0) == 1 else "Spot",
            "destination_masked": mask(row.get("address"), 7, 6),
            "txid_masked": mask(row.get("txId"), 10, 8),
            "withdrawal_id_masked": mask(row.get("id"), 8, 6),
            "withdraw_order_id": str(row.get("withdrawOrderId") or ""),
            "info": mask_info(row.get("info")),
        })
    cleaned.sort(key=lambda row: row["apply_time"], reverse=True)
    OUTPUT.write_text(json.dumps({
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_start": START.isoformat(),
        "source_end": end_all.isoformat(),
        "request_count": request_count,
        "record_count": len(cleaned),
        "records": cleaned,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"records": len(cleaned), "requests": request_count, "output": str(OUTPUT)}))


if __name__ == "__main__":
    main()
