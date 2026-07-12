"""Tests for dashboard comparisons and operational alerts."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import database as db


def test_dashboard_comparisons_and_alerts(mock_mongodb):
    now = int(time.time())
    today_start = now - (now % 86400)
    mock_mongodb.orders.insert_many([
        {"id": 1, "status": "delivered", "total_price": 10.0, "created_at": today_start + 1},
        {"id": 2, "status": "delivered", "total_price": 4.0, "created_at": today_start - 100},
        {"id": 3, "status": "payment_confirmed", "total_price": 8.0, "created_at": today_start, "paid_at": now - 1800},
        {"id": 4, "status": "manual_review", "total_price": 6.0, "created_at": today_start},
    ])
    mock_mongodb.audit_events.insert_one({"action": "system.error", "created_at": datetime.now(UTC)})

    data = db.dashboard_data()
    summary = data["summary"]
    alert_types = {alert["type"] for alert in data["alerts"]}

    assert summary["orders_day_delta"] == 2
    assert summary["revenue_day_delta"] == 14.0
    assert summary["paid_not_delivered"] == 1
    assert summary["failed_payments"] == 1
    assert {"paid_not_delivered", "payment_review", "recent_errors"} <= alert_types
