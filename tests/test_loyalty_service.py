"""Tests for seven-day customer loyalty levels."""

import time

import database as db
from app.domain import loyalty_service, order_service


def _paid_order(conn, order_id, user_id, amount):
    conn.orders.insert_one({
        "id": order_id,
        "user_id": user_id,
        "status": "delivered",
        "gross_total": amount,
        "total_price": amount,
    })


def test_levels_match_spend_thresholds(mock_mongodb):
    expected = [
        (30, "bronze", 8),
        (70, "silver", 16),
        (200, "platinum", 24),
        (500, "diamond", 30),
    ]
    for index, (amount, level, discount) in enumerate(expected, start=1):
        user_id = 1000 + index
        _paid_order(mock_mongodb, index, user_id, amount)
        benefit = loyalty_service.record_purchase(user_id)
        assert benefit["level"] == level
        assert benefit["discount_percent"] == discount
        assert benefit["expires_at"] > int(time.time()) + 6 * 86400


def test_active_level_discount_is_applied_to_new_order(mock_mongodb):
    db.add_service("AI", "🤖")
    offer_id = db.add_offer(1, "Premium", 100.0, 2)
    _paid_order(mock_mongodb, 90, 42, 70.0)
    loyalty_service.record_purchase(42)

    order = order_service.create_order(42, db.get_offer(offer_id))

    assert order["loyalty_level"] == "silver"
    assert order["loyalty_discount_percent"] == 16
    assert order["total_price"] == 84.0


def test_expired_level_has_no_discount(mock_mongodb):
    mock_mongodb.loyalty.insert_one({
        "user_id": 42, "level": "diamond", "discount_percent": 30, "expires_at": int(time.time()) - 1,
    })
    assert loyalty_service.discount_for_order(42, 100)["amount"] == 0
