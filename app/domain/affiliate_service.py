"""Simple referral program: 1 USDT for every 5 valid referrals."""
from __future__ import annotations

import time
from typing import Any

from pymongo.errors import DuplicateKeyError

import database as db

REFERRAL_TARGET = 5
REFERRAL_REWARD_CENTS = 100


def register_referral_link(referred_id: int, referrer_id: int) -> bool:
    """Register one unique valid referral and reward each group of five."""
    if referred_id == referrer_id:
        return False
    conn = db.get_conn()
    if not conn.users.find_one({"telegram_id": referrer_id}, {"_id": 1}):
        return False
    try:
        conn.referrals.insert_one({
            "referred_id": referred_id,
            "referrer_id": referrer_id,
            "valid": True,
            "created_at": int(time.time()),
        })
    except DuplicateKeyError:
        return False

    count = conn.referrals.count_documents({"referrer_id": referrer_id, "valid": {"$ne": False}})
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
        except DuplicateKeyError:
            pass
    return True


def on_confirmed_payment(user_id: int, order_id: int) -> None:
    """Kept as a compatibility hook; referrals no longer require a purchase."""
    return None


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
