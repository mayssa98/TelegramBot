"""Referral program with qualified members, daily caps and milestone rewards."""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from pymongo.errors import DuplicateKeyError

import database as db
from app.constants import PAID_STATUSES
from config import (
    AFFILIATE_DAILY_CAP,
    AFFILIATE_FIVE_REWARD_CENTS,
    AFFILIATE_QUALIFY_CENTS,
    AFFILIATE_TEN_REWARD_CENTS,
)

log = logging.getLogger(__name__)


def register_referral_link(referred_id: int, referrer_id: int) -> bool:
    """Attach a new user to an existing referrer, once and without self-referrals."""
    if referred_id == referrer_id:
        return False
    conn = db.get_conn()
    if not conn.users.find_one({"telegram_id": referrer_id}, {"_id": 1}):
        return False
    try:
        conn.referrals.insert_one({
            "referred_id": referred_id,
            "referrer_id": referrer_id,
            "qualified": False,
            "created_at": int(time.time()),
        })
        return True
    except DuplicateKeyError:
        return False


def _utc_day(timestamp: int | None = None) -> str:
    moment = datetime.fromtimestamp(timestamp or time.time(), UTC)
    return moment.strftime("%Y-%m-%d")


def _paid_total(user_id: int) -> float:
    rows = db.get_conn().orders.find({
        "user_id": user_id,
        "status": {"$in": [str(status) for status in PAID_STATUSES]},
    })
    return round(sum(float(row.get("gross_total", row.get("total_price", 0))) for row in rows), 2)


def on_confirmed_payment(user_id: int, order_id: int) -> dict[str, Any] | None:
    """Qualify one referred member after 10 USDT cumulative confirmed purchases.

    At most ten members per referrer and UTC day are counted. The fifth member
    awards 5 USDT; the tenth awards an additional 2 USDT.
    """
    conn = db.get_conn()
    referral = conn.referrals.find_one({"referred_id": user_id})
    if not referral or referral.get("qualified"):
        return None
    total = _paid_total(user_id)
    if round(total * 100) < AFFILIATE_QUALIFY_CENTS:
        return None

    day = _utc_day()
    referrer_id = referral["referrer_id"]
    counted_today = conn.referrals.count_documents({
        "referrer_id": referrer_id,
        "qualified_day": day,
    })
    if counted_today >= AFFILIATE_DAILY_CAP:
        return {
            "referrer_id": referrer_id,
            "qualified": False,
            "daily_cap_reached": True,
            "daily_count": counted_today,
            "rewarded": False,
            "reward_amount": 0,
        }

    result = conn.referrals.update_one(
        {"referred_id": user_id, "qualified": {"$ne": True}},
        {"$set": {
            "qualified": True,
            "qualified_at": int(time.time()),
            "qualified_day": day,
            "qualifying_order_id": order_id,
            "qualified_spend": total,
        }},
    )
    if result.modified_count != 1:
        return None

    daily_count = counted_today + 1
    reward_cents = 0
    if daily_count == 5:
        reward_cents = AFFILIATE_FIVE_REWARD_CENTS
    elif daily_count == 10:
        reward_cents = AFFILIATE_TEN_REWARD_CENTS

    rewarded = False
    if reward_cents:
        milestone = f"{day}:{daily_count}"
        try:
            conn.affiliate_rewards.insert_one({
                "referrer_id": referrer_id,
                "milestone": milestone,
                "day": day,
                "qualified_count": daily_count,
                "amount_cents": reward_cents,
                "created_at": int(time.time()),
            })
            conn.wallets.update_one(
                {"user_id": referrer_id},
                {"$inc": {"balance_cents": reward_cents}},
                upsert=True,
            )
            rewarded = True
        except DuplicateKeyError:
            pass

    db.audit_event(
        "affiliate.member_qualified",
        actor_id=referrer_id,
        details={"referred_id": user_id, "daily_count": daily_count, "reward_cents": reward_cents},
    )
    return {
        "referrer_id": referrer_id,
        "qualified": True,
        "daily_cap_reached": False,
        "daily_count": daily_count,
        "rewarded": rewarded,
        "reward_amount": reward_cents / 100,
    }


def get_stats(user_id: int) -> dict[str, Any]:
    conn = db.get_conn()
    day = _utc_day()
    total_referrals = conn.referrals.count_documents({"referrer_id": user_id})
    qualified = conn.referrals.count_documents({"referrer_id": user_id, "qualified": True})
    qualified_today = conn.referrals.count_documents({
        "referrer_id": user_id,
        "qualified_day": day,
    })
    wallet = conn.wallets.find_one({"user_id": user_id}) or {}
    rewards = list(conn.affiliate_rewards.find({"referrer_id": user_id}))
    earned_cents = sum(int(row.get("amount_cents", 0)) for row in rewards)
    return {
        "referrals": total_referrals,
        "qualified_referrals": qualified,
        "pending_referrals": max(0, total_referrals - qualified),
        "qualified_today": qualified_today,
        "daily_remaining": max(0, AFFILIATE_DAILY_CAP - qualified_today),
        "balance_cents": int(wallet.get("balance_cents", 0)),
        "earned_cents": earned_cents,
    }
