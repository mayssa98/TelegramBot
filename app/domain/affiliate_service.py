"""Referral program: 2 USDT for every 10 purchase-qualified referrals."""
from __future__ import annotations

import time
from typing import Any

from pymongo.errors import DuplicateKeyError

import database as db
from config import AFFILIATE_MIN_PURCHASE_CENTS

REFERRAL_TARGET = 10
REFERRAL_REWARD_CENTS = 200


def register_referral_link(referred_id: int, referrer_id: int) -> bool:
    """Register one unique pending referral from a personal invitation link."""
    if referred_id == referrer_id:
        return False
    conn = db.get_conn()
    if not conn.users.find_one({"telegram_id": referrer_id}, {"_id": 1}):
        return False
    try:
        conn.referrals.insert_one({
            "referred_id": referred_id,
            "referrer_id": referrer_id,
            "valid": False,
            "created_at": int(time.time()),
        })
    except DuplicateKeyError:
        return False
    return True


def on_confirmed_payment(user_id: int, order_id: int) -> dict[str, Any] | None:
    """Validate a pending referral after the referred user buys for at least 1 USDT."""
    conn = db.get_conn()
    order = conn.orders.find_one({"id": int(order_id), "user_id": int(user_id)})
    if not order:
        return None
    total_cents = round(float(order.get("total_price") or 0) * 100)
    if total_cents < AFFILIATE_MIN_PURCHASE_CENTS:
        return None
    referral = conn.referrals.find_one({
        "referred_id": int(user_id),
        "valid": {"$ne": True},
    })
    if not referral:
        return None
    updated = conn.referrals.update_one(
        {"_id": referral["_id"], "valid": {"$ne": True}},
        {
            "$set": {
                "valid": True,
                "qualified_order_id": int(order_id),
                "qualified_purchase_cents": total_cents,
                "qualified_at": int(time.time()),
            }
        },
    )
    if updated.modified_count != 1:
        return None
    referrer_id = int(referral["referrer_id"])
    count = conn.referrals.count_documents({"referrer_id": referrer_id, "valid": {"$ne": False}})
    rewarded = False
    if count % REFERRAL_TARGET == 0:
        milestone = count // REFERRAL_TARGET
        try:
            conn.affiliate_rewards.insert_one({
                "referrer_id": referrer_id,
                "milestone": milestone,
                "valid_referrals": count,
                "amount_cents": REFERRAL_REWARD_CENTS,
                "created_at": int(time.time()),
            })
            conn.wallets.update_one(
                {"user_id": referrer_id},
                {"$inc": {"balance_cents": REFERRAL_REWARD_CENTS}},
                upsert=True,
            )
            rewarded = True
        except DuplicateKeyError:
            pass
    return {
        "referrer_id": referrer_id,
        "daily_count": count,
        "valid_referrals": count,
        "rewarded": rewarded,
        "reward_amount": REFERRAL_REWARD_CENTS / 100,
    }


def get_stats(user_id: int) -> dict[str, Any]:
    conn = db.get_conn()
    referrals = conn.referrals.count_documents({
        "referrer_id": user_id,
        "valid": {"$ne": False},
    })
    wallet = conn.wallets.find_one({"user_id": user_id}) or {}
    rewards = list(conn.affiliate_rewards.find({"referrer_id": user_id}))
    earned_cents = sum(int(row.get("amount_cents", 0)) for row in rewards)
    return {
        "referrals": referrals,
        "valid_referrals": referrals,
        "progress": referrals % REFERRAL_TARGET,
        "remaining": REFERRAL_TARGET - (referrals % REFERRAL_TARGET) if referrals % REFERRAL_TARGET else REFERRAL_TARGET,
        "balance_cents": int(wallet.get("balance_cents", 0)),
        "earned_cents": earned_cents,
    }
