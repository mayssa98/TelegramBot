"""Tests for server-side dashboard filters and pagination."""

from __future__ import annotations

from datetime import UTC, datetime

from app.web import dashboard_api


def test_order_filters_and_pagination(mock_mongodb):
    mock_mongodb.orders.insert_many([
        {"id": 1, "user_id": 10, "offer_id": 5, "offer_name": "Alpha", "service_name": "AI", "status": "pending_payment", "created_at": 1},
        {"id": 2, "user_id": 20, "offer_id": 6, "offer_name": "Beta", "service_name": "Video", "status": "delivered", "created_at": 2},
        {"id": 3, "user_id": 10, "offer_id": 5, "offer_name": "Alpha Plus", "service_name": "AI", "status": "delivered", "created_at": 3},
    ])

    result = dashboard_api.list_orders({"status": ["delivered"], "page": ["1"], "per_page": ["1"]})

    assert result["total"] == 2
    assert result["pages"] == 2
    assert result["items"][0]["id"] == 3


def test_order_search_matches_numeric_customer(mock_mongodb):
    mock_mongodb.orders.insert_one({
        "id": 9,
        "user_id": 12345,
        "offer_name": "Netflix",
        "service_name": "VOD",
        "status": "delivered",
        "created_at": 1,
    })

    result = dashboard_api.list_orders({"search": ["12345"]})

    assert result["total"] == 1


def test_ticket_filters(mock_mongodb):
    now = datetime.now(UTC)
    mock_mongodb.support_tickets.insert_many([
        {"id": 1, "user_id": 10, "status": "waiting_admin", "updated_at": now},
        {"id": 2, "user_id": 10, "status": "closed", "updated_at": now},
    ])

    result = dashboard_api.list_tickets({"status": ["waiting_admin"]})

    assert result["total"] == 1
    assert result["items"][0]["id"] == 1
