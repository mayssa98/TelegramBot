"""Customer wallet top-ups and atomic balance usage."""
from __future__ import annotations

import re
import time
from typing import Any

from pymongo.errors import DuplicateKeyError

import database as db
from payment_verifier import verify_incoming_transfer, verify_incoming_transfer_by_memo


def balance_cents(user_id: int) -> int:
    wallet = db.get_conn().wallets.find_one({"user_id": user_id}) or {}
    return max(0, int(wallet.get("balance_cents", 0)))


def claim_transfer(user_id: int, txid: str) -> dict[str, Any]:
    txid = (txid or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", txid):
        return {"status": "failed", "code": "invalid_format", "message": "TXID invalide."}
    conn = db.get_conn()
    if conn.wallet_topups.find_one({"txid": txid}):
        return {"status": "failed", "code": "already_used", "message": "Ce TXID a déjà été crédité."}
    verification = verify_incoming_transfer(txid, minimum_amount=1)
    if verification["status"] != "confirmed":
        return {
            "status": verification["status"],
            "code": verification.get("code"),
            "message": verification.get("reason"),
        }
    amount_cents = round(float(verification["amount"]) * 100)
    try:
        conn.wallet_topups.insert_one({
            "txid": txid,
            "user_id": user_id,
            "amount_cents": amount_cents,
            "currency": verification["currency"],
            "created_at": int(time.time()),
        })
    except DuplicateKeyError:
        return {"status": "failed", "code": "already_used", "message": "Ce TXID a déjà été crédité."}
    conn.wallets.update_one(
        {"user_id": user_id},
        {"$inc": {"balance_cents": amount_cents}},
        upsert=True,
    )
    db.audit_event("wallet.topup_confirmed", actor_id=user_id, details={"txid": txid, "amount_cents": amount_cents})
    return {"status": "confirmed", "amount": amount_cents / 100, "balance": balance_cents(user_id) / 100}


def claim_transfer_by_memo(user_id: int, created_at: int) -> dict[str, Any]:
    """Credit a recent transfer identified by the customer Telegram-ID memo."""
    conn = db.get_conn()
    used_txids = conn.wallet_topups.distinct("txid")
    verification = verify_incoming_transfer_by_memo(
        user_id,
        minimum_amount=1,
        created_at=created_at,
        used_txids=used_txids,
    )
    if verification["status"] != "confirmed":
        return verification
    txid = verification["txid"]
    amount_cents = round(float(verification["amount"]) * 100)
    try:
        conn.wallet_topups.insert_one({
            "txid": txid,
            "user_id": user_id,
            "amount_cents": amount_cents,
            "currency": verification["currency"],
            "verification_method": "memo",
            "created_at": int(time.time()),
        })
    except DuplicateKeyError:
        return {"status": "failed", "code": "already_used", "message": "This transfer was already credited."}
    conn.wallets.update_one(
        {"user_id": user_id},
        {"$inc": {"balance_cents": amount_cents}},
        upsert=True,
    )
    db.audit_event(
        "wallet.topup_confirmed",
        actor_id=user_id,
        details={"txid": txid, "amount_cents": amount_cents, "method": "memo"},
    )
    return {
        "status": "confirmed",
        "amount": amount_cents / 100,
        "balance": balance_cents(user_id) / 100,
        "txid": txid,
    }

def apply_balance(user_id: int, amount: float) -> float:
    requested = max(0, round(amount * 100))
    if not requested:
        return 0.0
    conn = db.get_conn()
    available = balance_cents(user_id)
    used = min(available, requested)
    if not used:
        return 0.0
    result = conn.wallets.update_one(
        {"user_id": user_id, "balance_cents": {"$gte": used}},
        {"$inc": {"balance_cents": -used}},
    )
    return used / 100 if result.modified_count else 0.0


def refund_balance(user_id: int, amount: float, order_id: int) -> bool:
    cents = round(max(0, amount) * 100)
    if not cents:
        return False
    conn = db.get_conn()
    result = conn.orders.update_one(
        {"id": order_id, "wallet_refunded": {"$ne": True}},
        {"$set": {"wallet_refunded": True}},
    )
    if result.modified_count != 1:
        return False
    conn.wallets.update_one({"user_id": user_id}, {"$inc": {"balance_cents": cents}}, upsert=True)
    return True
