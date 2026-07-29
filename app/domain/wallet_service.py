"""Customer wallet top-ups and atomic balance usage."""
from __future__ import annotations

import re
import time
from typing import Any

from pymongo import ReturnDocument
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


def submit_onchain_topup(
    user_id: int, txid: str, amount: float, network: str,
) -> dict[str, Any]:
    """Create a manual-review BSC/Polygon wallet top-up."""
    txid = (txid or "").strip()
    network = str(network or "").lower()
    if network not in {"bsc", "polygon"}:
        return {"status": "failed", "code": "invalid_network", "message": "Réseau invalide."}
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", txid):
        return {"status": "failed", "code": "invalid_format", "message": "TXID invalide."}
    amount_cents = round(float(amount) * 100)
    if amount_cents < 100:
        return {"status": "failed", "code": "minimum", "message": "Minimum: 1 USDT."}

    conn = db.get_conn()
    topup_id = db._next_id("wallet_topups")
    try:
        conn.wallet_topups.insert_one({
            "id": topup_id,
            "txid": txid,
            "user_id": int(user_id),
            "amount_cents": amount_cents,
            "currency": "USDT",
            "network": network,
            "verification_method": "manual_onchain",
            "status": "manual_review",
            "created_at": int(time.time()),
        })
    except DuplicateKeyError:
        return {
            "status": "failed",
            "code": "already_used",
            "message": "Ce TXID a déjà été soumis.",
        }
    db.audit_event(
        "wallet.topup_manual_review",
        actor_id=user_id,
        details={"topup_id": topup_id, "network": network, "amount_cents": amount_cents},
    )
    return {
        "status": "manual_review",
        "id": topup_id,
        "txid": txid,
        "amount": amount_cents / 100,
        "network": network,
        "user_id": int(user_id),
    }


def approve_onchain_topup(topup_id: int, admin_id: int) -> dict[str, Any] | None:
    """Atomically approve a pending top-up and credit its wallet once."""
    conn = db.get_conn()
    topup = conn.wallet_topups.find_one_and_update(
        {"id": int(topup_id), "status": "manual_review"},
        {"$set": {
            "status": "confirmed",
            "approved_by": int(admin_id),
            "approved_at": int(time.time()),
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not topup:
        return None
    conn.wallets.update_one(
        {"user_id": topup["user_id"]},
        {"$inc": {"balance_cents": int(topup["amount_cents"])}},
        upsert=True,
    )
    topup["balance"] = balance_cents(topup["user_id"]) / 100
    db.audit_event(
        "wallet.topup_confirmed_manual",
        actor_id=admin_id,
        details={"topup_id": topup_id, "user_id": topup["user_id"]},
    )
    return topup


def reject_onchain_topup(topup_id: int, admin_id: int) -> dict[str, Any] | None:
    conn = db.get_conn()
    topup = conn.wallet_topups.find_one_and_update(
        {"id": int(topup_id), "status": "manual_review"},
        {"$set": {
            "status": "rejected",
            "rejected_by": int(admin_id),
            "rejected_at": int(time.time()),
        }},
        return_document=ReturnDocument.AFTER,
    )
    if topup:
        db.audit_event(
            "wallet.topup_rejected",
            actor_id=admin_id,
            details={"topup_id": topup_id, "user_id": topup["user_id"]},
        )
    return topup


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
