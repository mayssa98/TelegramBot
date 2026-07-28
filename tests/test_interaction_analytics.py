from __future__ import annotations

import database as db


def test_interaction_analytics_tracks_daily_users_types_and_details(mock_mongodb):
    db.log_interaction(
        42,
        first_name="Test",
        full_name="Test Buyer",
        username="buyer",
        interaction_type="button",
        action="buy:17",
        screen="Offer screen",
    )
    db.log_interaction(
        42,
        first_name="Test",
        full_name="Test Buyer",
        username="buyer",
        interaction_type="message",
        content="hello",
    )

    result = db.interaction_analytics(days=30, limit=1000)

    assert result["summary"]["total"] == 2
    assert result["summary"]["today"] == 2
    assert result["summary"]["active_today"] == 1
    assert result["summary"]["live_users"] == 1
    assert result["summary"]["button_clicks"] == 1
    assert result["summary"]["messages"] == 1
    assert sum(point["count"] for point in result["daily"]) == 2
    assert len(result["events"]) == 2
    assert result["events"][0]["full_name"] == "Test Buyer"


def test_user_activity_summary_includes_recent_today_and_total(mock_mongodb):
    mock_mongodb.users.insert_many([
        {"telegram_id": 42},
        {"telegram_id": 43},
    ])
    db.log_interaction(42, interaction_type="button", action="home")

    result = db.user_activity_summary()

    assert result == {
        "online_now": 1,
        "active_today": 1,
        "total_users": 2,
    }
