"""Tests for the 2 USDT / 10 purchase-qualified referrals program."""

from app.domain import affiliate_service


def _prepare_referrer(mock_mongodb, referrer_id=999):
    mock_mongodb.users.insert_one({"telegram_id": referrer_id})


def _register_and_buy(mock_mongodb, user_id, referrer_id, order_id, total_price):
    mock_mongodb.users.insert_one({"telegram_id": user_id})
    assert affiliate_service.register_referral_link(user_id, referrer_id)
    mock_mongodb.orders.insert_one({
        "id": order_id,
        "user_id": user_id,
        "total_price": total_price,
    })
    return affiliate_service.on_confirmed_payment(user_id, order_id)


def test_register_referral_rejects_self_referral(mock_mongodb):
    _prepare_referrer(mock_mongodb, 111)
    assert affiliate_service.register_referral_link(111, 111) is False


def test_referral_requires_a_purchase_of_at_least_one_usdt(mock_mongodb):
    _prepare_referrer(mock_mongodb)

    below_minimum = _register_and_buy(mock_mongodb, 100, 999, 1, 0.99)
    assert below_minimum is None
    assert mock_mongodb.referrals.find_one({"referred_id": 100})["valid"] is False

    exact_minimum = _register_and_buy(mock_mongodb, 101, 999, 2, 1.00)
    assert exact_minimum["valid_referrals"] == 1
    assert exact_minimum["rewarded"] is False
    assert mock_mongodb.referrals.find_one({"referred_id": 101})["valid"] is True


def test_ten_qualified_referrals_reward_two_usdt(mock_mongodb):
    _prepare_referrer(mock_mongodb)
    result = None
    for index in range(10):
        result = _register_and_buy(mock_mongodb, 100 + index, 999, 1000 + index, 1.00)

    assert result["rewarded"] is True
    assert result["reward_amount"] == 2.0
    stats = affiliate_service.get_stats(999)
    assert stats["valid_referrals"] == 10
    assert stats["balance_cents"] == 200
    assert stats["earned_cents"] == 200


def test_confirmed_purchase_qualifies_each_referral_only_once(mock_mongodb):
    _prepare_referrer(mock_mongodb)
    result = _register_and_buy(mock_mongodb, 100, 999, 1, 5.00)

    assert result["valid_referrals"] == 1
    assert affiliate_service.on_confirmed_payment(100, 1) is None
    assert affiliate_service.get_stats(999)["valid_referrals"] == 1


def test_each_new_group_of_ten_rewards_two_usdt(mock_mongodb):
    _prepare_referrer(mock_mongodb)
    for index in range(20):
        _register_and_buy(mock_mongodb, 100 + index, 999, 1000 + index, 1.00)

    stats = affiliate_service.get_stats(999)
    assert stats["valid_referrals"] == 20
    assert stats["balance_cents"] == 400
    assert stats["earned_cents"] == 400