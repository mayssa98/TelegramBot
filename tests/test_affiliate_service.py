"""Tests for the simple 2 USDT / 10 valid referrals program."""

from app.domain import affiliate_service


def _prepare_referrer(conn, referrer_id=999):
    conn.users.insert_one({"telegram_id": referrer_id})


def test_register_referral_rejects_self_referral(mock_mongodb):
    _prepare_referrer(mock_mongodb, 111)
    assert affiliate_service.register_referral_link(111, 111) is False


def test_ten_unique_valid_referrals_reward_two_usdt(mock_mongodb):
    _prepare_referrer(mock_mongodb)
    for index in range(10):
        user_id = 100 + index
        mock_mongodb.users.insert_one({"telegram_id": user_id})
        assert affiliate_service.register_referral_link(user_id, 999)

    stats = affiliate_service.get_stats(999)
    assert stats["valid_referrals"] == 10
    assert stats["balance_cents"] == 200
    assert stats["earned_cents"] == 200


def test_duplicate_referral_is_not_counted_or_rewarded_twice(mock_mongodb):
    _prepare_referrer(mock_mongodb)
    mock_mongodb.users.insert_one({"telegram_id": 100})

    assert affiliate_service.register_referral_link(100, 999)
    assert affiliate_service.register_referral_link(100, 999) is False
    assert affiliate_service.get_stats(999)["valid_referrals"] == 1


def test_each_new_group_of_ten_rewards_two_usdt(mock_mongodb):
    _prepare_referrer(mock_mongodb)
    for index in range(20):
        user_id = 100 + index
        mock_mongodb.users.insert_one({"telegram_id": user_id})
        assert affiliate_service.register_referral_link(user_id, 999)

    assert affiliate_service.get_stats(999)["balance_cents"] == 400
