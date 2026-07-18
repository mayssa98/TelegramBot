"""Tests for server-side dashboard filters and pagination."""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import UTC, datetime

import pytest

from api.dashboard import render_dashboard
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


def test_order_date_service_and_amount_sort(mock_mongodb):
    mock_mongodb.offers.insert_many([{"id": 700, "service_id": 200}, {"id": 800, "service_id": 300}])
    mock_mongodb.orders.insert_many([
        {"id": 1, "offer_id": 700, "total_price": 5.0, "created_at": 100},
        {"id": 2, "offer_id": 700, "total_price": 12.0, "created_at": 200},
        {"id": 3, "offer_id": 800, "total_price": 50.0, "created_at": 200},
    ])

    result = dashboard_api.list_orders({"service_id": ["200"], "sort": ["amount"]})

    assert [item["id"] for item in result["items"]] == [2, 1]


def test_ticket_filters(mock_mongodb):
    now = datetime.now(UTC)
    mock_mongodb.support_tickets.insert_many([
        {"id": 1, "user_id": 10, "status": "waiting_admin", "updated_at": now},
        {"id": 2, "user_id": 10, "status": "closed", "updated_at": now},
    ])

    result = dashboard_api.list_tickets({"status": ["waiting_admin"]})

    assert result["total"] == 1
    assert result["items"][0]["id"] == 1


def test_inventory_never_exposes_encrypted_payload(mock_mongodb):
    mock_mongodb.inventory.insert_one({
        "offer_id": 4,
        "payload": "encrypted-secret",
        "fingerprint": "hash",
        "masked_preview": "us***@example.com",
        "status": "available",
        "created_at": 1,
    })

    result = dashboard_api.list_inventory({"offer_id": ["4"]})

    assert result["total"] == 1
    assert result["items"][0]["masked_preview"] == "us***@example.com"
    assert "payload" not in result["items"][0]
    assert "fingerprint" not in result["items"][0]


def test_customer_detail_metrics(mock_mongodb):
    mock_mongodb.users.insert_one({"telegram_id": 42, "username": "buyer", "created_at": 1})
    mock_mongodb.orders.insert_many([
        {"id": 1, "user_id": 42, "status": "delivered", "total_price": 7.5, "created_at": 2},
        {"id": 2, "user_id": 42, "status": "pending_payment", "total_price": 3.0, "created_at": 3},
    ])

    customer = dashboard_api.customer_detail(42)

    assert customer is not None
    assert customer["order_count"] == 2
    assert customer["paid_order_count"] == 1
    assert customer["total_spent"] == 7.5


def test_dashboard_renders_mongodb_dates():
    page = render_dashboard({
        "summary": {},
        "orders": [],
        "users": [{"telegram_id": 1, "created_at": datetime.now(UTC)}],
        "tickets": [],
        "services": [],
        "audits": [],
    })

    assert "<!doctype html>" in page.lower()
    assert "customer-detail-modal" in page
    assert 'id="inventory-table"' in page
    assert "revealInventory" in page
    assert "toggleInventory" in page
    assert "/admin/api/inventory-export" in page


def test_dashboard_support_tab_has_real_page_link():
    page = render_dashboard({"summary": {}, "alerts": []}, active_tab="support")

    assert 'href="/admin/support" data-tab="support" class="active"' in page
    assert 'id="support" class="panel active"' in page
    assert "__ACTIVE_" not in page
    assert "__PANEL_" not in page


def test_dashboard_contains_order_management_controls():
    page = render_dashboard({"summary": {}, "alerts": []}, active_tab="orders")

    assert "updateOrderAdmin" in page
    assert "manualDeliverOrder" in page
    assert "manual_deliver_order" in page
    assert "update_order_admin" in page


def test_dashboard_contains_product_sync_fields():
    page = render_dashboard({"summary": {}, "alerts": []}, active_tab="catalog")

    assert "Nouveau produit" in page
    assert "Catalogue par defaut" in page
    assert 'name="description"' in page
    assert 'name="initial_inventory"' in page
    assert "Comptes initiaux — stock automatique (# = 1 produit)" in page
    assert 'name="stock"' not in page
    assert "Livraison :" in page


def test_dashboard_javascript_syntax_is_valid(tmp_path):
    if not shutil.which("node"):
        pytest.skip("node is not installed")

    page = render_dashboard({"summary": {}, "alerts": [], "services": []}, active_tab="catalog")
    script = re.search(r"<script>(.*?)</script>", page, flags=re.S).group(1)
    script_path = tmp_path / "dashboard.js"
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(["node", "--check", str(script_path)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
