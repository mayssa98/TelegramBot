"""Tests for qualified referral members and daily rewards."""

import database as db
from app.domain import affiliate_service


def _users_and_referrals(conn, referrer_id=999, count=10):
    conn.users.insert_one({"telegram_id": referrer_id})
    for index in range(count):
        user_id = 100 + index
        conn.users.insert_one({"telegram_id": user_id})
        assert affiliate_service.register_referral_link(user_id, referrer_id)


def test_register_referral_rejects_self_referral(mock_mongodb):
    mock_mongodb.users.insert_one({"telegram_id": 111})
    assert affiliate_service.register_referral_link(111, 111) is False


def test_member_qualifies_after_ten_dollars(mock_mongodb):
    _users_and_referrals(mock_mongodb, count=1)
    mock_mongodb.orders.insert_one({
        "id": 1, "user_id": 100, "status": "delivered", "total_price": 10.0,
    })

    result = affiliate_service.on_confirmed_payment(100, 1)

    assert result["qualified"] is True
    assert result["daily_count"] == 1
    assert result["rewarded"] is False


def test_fifth_and_tenth_daily_members_reward_wallet(mock_mongodb):
    _users_and_referrals(mock_mongodb)
    rewards = []
    for index in range(10):
        user_id = 100 + index
        order_id = index + 1
        mock_mongodb.orders.insert_one({
            "id": order_id, "user_id": user_id, "status": "delivered", "total_price": 10.0,
        })
        result = affiliate_service.on_confirmed_payment(user_id, order_id)
        if result["rewarded"]:
            rewards.append(result["reward_amount"])

    assert rewards == [5.0, 2.0]
    assert affiliate_service.get_stats(999)["balance_cents"] == 700


def test_daily_cap_stops_the_eleventh_member(mock_mongodb):
    _users_and_referrals(mock_mongodb, count=11)
    for index in range(11):
        user_id = 100 + index
        order_id = index + 1
        mock_mongodb.orders.insert_one({
            "id": order_id, "user_id": user_id, "status": "delivered", "total_price": 10.0,
        })
        result = affiliate_service.on_confirmed_payment(user_id, order_id)

    assert result["daily_cap_reached"] is True
    assert db.get_conn().referrals.find_one({"referred_id": 110})["qualified"] is False
