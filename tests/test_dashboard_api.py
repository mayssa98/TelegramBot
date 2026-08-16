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
    assert result["analytics"]["total"] == 3
    assert result["analytics"]["delivered"] == 2
    assert result["analytics"]["statuses"] == {"pending_payment": 1, "delivered": 2}


def test_pending_onchain_topups_include_customer_and_explorer(mock_mongodb):
    mock_mongodb.users.insert_one({"telegram_id": 42, "username": "buyer", "first_name": "Buyer"})
    mock_mongodb.wallet_topups.insert_many([
        {
            "id": 7,
            "user_id": 42,
            "txid": "0xabcdef1234567890",
            "amount_cents": 1250,
            "currency": "USDT",
            "network": "bsc",
            "verification_method": "manual_onchain",
            "status": "manual_review",
            "created_at": 10,
        },
        {
            "id": 8,
            "user_id": 42,
            "txid": "ignored",
            "amount_cents": 500,
            "network": "polygon",
            "verification_method": "manual_onchain",
            "status": "confirmed",
            "created_at": 20,
        },
    ])

    result = dashboard_api.list_wallet_topups({})

    assert result["total"] == 1
    assert result["items"][0]["username"] == "buyer"
    assert result["items"][0]["amount"] == 12.5
    assert result["items"][0]["explorer_url"].startswith("https://bscscan.com/tx/")


def test_customer_filters_and_metric_sort(mock_mongodb):
    mock_mongodb.users.insert_many([
        {"telegram_id": 10, "username": "active", "banned": False, "created_at": 10},
        {"telegram_id": 20, "username": "blocked", "banned": True, "created_at": 20},
        {"telegram_id": 30, "username": "empty", "banned": False, "created_at": 30},
    ])
    mock_mongodb.wallets.insert_many([
        {"user_id": 10, "balance_cents": 500},
        {"user_id": 20, "balance_cents": 1200},
    ])
    mock_mongodb.orders.insert_many([
        {"id": 1, "user_id": 10, "status": "delivered", "total_price": 4},
        {"id": 2, "user_id": 20, "status": "delivered", "total_price": 9},
        {"id": 3, "user_id": 20, "status": "delivered", "total_price": 3},
    ])

    active_funded = dashboard_api.list_customers({
        "status": ["active"],
        "wallet": ["funded"],
    })
    without_orders = dashboard_api.list_customers({"orders": ["without_orders"]})
    by_balance = dashboard_api.list_customers({"sort": ["balance"]})

    assert [item["telegram_id"] for item in active_funded["items"]] == [10]
    assert [item["telegram_id"] for item in without_orders["items"]] == [30]
    assert [item["telegram_id"] for item in by_balance["items"]] == [20, 10, 30]


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


def test_order_search_can_target_txid_or_product_name(mock_mongodb):
    mock_mongodb.orders.insert_many([
        {"id": 1, "user_id": 10, "offer_name": "ChatGPT Plus", "txid": "TX-ALPHA-99", "created_at": 1},
        {"id": 2, "user_id": 20, "offer_name": "Canva Pro", "txid": "TX-BETA-12", "created_at": 2},
    ])

    by_txid = dashboard_api.list_orders({"search": ["alpha"], "search_field": ["txid"]})
    by_name = dashboard_api.list_orders({"search": ["canva"], "search_field": ["name"]})

    assert [item["id"] for item in by_txid["items"]] == [1]
    assert [item["id"] for item in by_name["items"]] == [2]


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


def test_ticket_search_uses_full_collection(mock_mongodb):
    mock_mongodb.support_tickets.insert_many([
        {"id": 4, "user_id": 10, "category": "Paiement", "message": "TXID manquant", "updated_at": 1},
        {"id": 5, "user_id": 20, "category": "Stock", "message": "Produit absent", "updated_at": 2},
    ])

    result = dashboard_api.list_tickets({"search": ["txid"], "search_field": ["message"]})

    assert [item["id"] for item in result["items"]] == [4]


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
    mock_mongodb.wallets.insert_one({"user_id": 42, "balance_cents": 1234})
    mock_mongodb.orders.insert_many([
        {"id": 1, "user_id": 42, "status": "delivered", "total_price": 7.5, "created_at": 2},
        {"id": 2, "user_id": 42, "status": "pending_payment", "total_price": 3.0, "created_at": 3},
    ])

    customer = dashboard_api.customer_detail(42)

    assert customer is not None
    assert customer["order_count"] == 2
    assert customer["paid_order_count"] == 1
    assert customer["total_spent"] == 7.5
    assert customer["wallet_balance"] == 12.34


def test_customer_detail_returns_complete_order_history(mock_mongodb):
    mock_mongodb.users.insert_one({"telegram_id": 42, "username": "buyer"})
    mock_mongodb.orders.insert_many([
        {"id": index, "user_id": 42, "status": "delivered", "created_at": index}
        for index in range(1, 56)
    ])

    customer = dashboard_api.customer_detail(42)

    assert customer is not None
    assert len(customer["orders"]) == 55
    assert customer["orders"][0]["id"] == 55


def test_order_detail_exposes_manual_delivery_and_customer(mock_mongodb):
    mock_mongodb.users.insert_one({"telegram_id": 42, "username": "buyer", "first_name": "Sam"})
    mock_mongodb.orders.insert_one({
        "id": 7,
        "user_id": 42,
        "status": "delivered",
        "delivery_text": "login@example.com\nsecret-password",
    })

    order = dashboard_api.order_detail(7)

    assert order is not None
    assert order["delivery_content"] == "login@example.com\nsecret-password"
    assert order["customer"]["username"] == "buyer"


def test_order_detail_decrypts_automatic_delivery(mock_mongodb):
    import database as db

    cipher = db._fernet()
    mock_mongodb.orders.insert_one({
        "id": 8,
        "user_id": 99,
        "status": "delivered",
        "delivery_text": "[encrypted automatic delivery]",
    })
    mock_mongodb.inventory.insert_many([
        {
            "id": 1,
            "delivered_order_id": 8,
            "status": "delivered",
            "payload": cipher.encrypt(b"first-login:first-secret").decode(),
        },
        {
            "id": 2,
            "delivered_order_id": 8,
            "status": "delivered",
            "payload": cipher.encrypt(b"second-login:second-secret").decode(),
        },
    ])

    order = dashboard_api.order_detail(8)

    assert order is not None
    assert order["delivery_content"] == (
        "first-login:first-secret\n\nsecond-login:second-secret"
    )


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


def test_dashboard_interactions_page_has_live_graphs_and_detail_table():
    page = render_dashboard({
        "summary": {},
        "alerts": [],
        "interactions": {
            "summary": {"total": 8, "today": 3, "active_today": 2, "live_users": 1},
            "daily": [{"date": "2026-07-26", "count": 3}],
            "service_clicks": {
                "total": 3,
                "services": [{"service_id": 7, "name": "Streaming", "count": 3}],
                "daily": [{
                    "date": "2026-07-26", "total": 3,
                    "services": [{"service_id": 7, "name": "Streaming", "count": 3}],
                }],
            },
            "types": {"button": 2, "message": 1},
            "events": [{
                "created_at": 1785024000,
                "user_id": 42,
                "full_name": "Test Buyer",
                "username": "buyer",
                "interaction_type": "button",
                "action": "buy:17",
                "content": "",
                "screen": "Offer screen",
            }],
        },
    }, active_tab="interactions")

    assert 'href="/admin/interactions"' in page
    assert 'id="interactions" class="panel active"' in page
    assert 'id="interactions-daily-chart"' in page
    assert 'id="service-clicks-daily"' in page
    assert "Services consultés par jour" in page
    assert "@media (max-width: 600px)" in page
    assert 'id="interactions-table"' in page
    assert "Interactions clients en direct" in page
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


def test_dashboard_has_mailreader_api_products_management():
    page = render_dashboard(
        {"summary": {}, "alerts": [], "services": []},
        active_tab="api-products",
        dashboard_write_token="safe-write-token",
    )

    assert 'href="/admin/api-products"' in page
    assert 'id="api-products" class="panel active"' in page
    assert "/admin/api/reseller-products" in page
    assert "save_reseller_product" in page
    assert "Centre des API" in page
    assert "Dashboard des API" in page
    assert "Shamekh’s bot" in page
    assert "selectApiProvider('shamekh')" in page
    assert "Kakao Shop" in page
    assert "selectApiProvider('kakao')" in page
    assert "VEX Reseller" in page
    assert "selectApiProvider('vex')" in page
    assert "selectApiProvider('canboso')" in page
    assert "Clés Buyer API" in page
    assert "/api/swagger" in page
    assert "createBuyerApiKey" in page
    assert "revokeBuyerApiKey" in page
    assert "Produits & services" in page
    assert "Description, prix & garantie" in page
    assert "openApiProductEditor" in page
    assert "Votre prix client" in page
    assert "Service affiché dans le bot" in page
    assert "Créer un nouveau service" in page
    assert "Nom visible du produit" in page
    assert "Garantie affichée dans le bot" in page
    assert "Aperçu dans le bot" in page
    assert "Publier et revendre dans le bot" in page
    assert "low_stock_threshold" in page
    assert 'const dashboardWriteToken = "safe-write-token"' in page
    assert '"X-Dashboard-Write-Token": dashboardWriteToken' in page
    assert "__ACTIVE_" not in page
    assert "__PANEL_" not in page


def test_dashboard_attaches_write_token_to_every_admin_request():
    page = render_dashboard(
        {"summary": {}, "alerts": [], "services": []},
        active_tab="catalog",
        dashboard_write_token="safe-write-token",
    )

    assert "window.fetch = (input, options = {}) =>" in page
    assert 'requestUrl.pathname.startsWith("/admin")' in page
    assert 'headers.set("X-Dashboard-Write-Token", dashboardWriteToken)' in page
    assert 'credentials: "same-origin"' in page


def test_dashboard_uses_midnight_merchant_command_center():
    page = render_dashboard({
        "summary": {"orders": 2, "pending_orders": 1, "open_tickets": 1},
        "alerts": [],
        "services": [],
        "orders": [],
        "interactions": {"summary": {"live_users": 2, "active_today": 5}},
    })

    assert "Midnight Merchant" in page
    assert 'class="merchant-topbar"' in page
    assert 'id="overview-orders-table"' in page
    assert "Actions rapides" in page
    assert "Fournisseur API" in page
    assert "runGlobalSearch" in page
    assert "syncSupplierCatalog" in page


def test_dashboard_has_notification_center_without_auto_refresh():
    page = render_dashboard({"summary": {}, "alerts": []})

    assert 'id="notification-panel"' in page
    assert 'id="notification-badge"' in page
    assert "admin-notifications-v1" in page
    assert "Notification.requestPermission()" in page
    assert "setInterval(() => refreshDashboardData(true), 15000)" not in page
    assert 'document.addEventListener("visibilitychange"' not in page


def test_dashboard_contains_binance_health_test():
    page = render_dashboard({"summary": {}, "alerts": []}, active_tab="overview")

    assert "Tester Binance" in page
    assert "/admin/api/binance-health" in page
    assert "testBinanceConnection" in page


def test_dashboard_contains_telegram_webhook_repair():
    page = render_dashboard({"summary": {}, "alerts": []}, active_tab="overview")

    assert "Réparer Telegram" in page
    assert "/admin/api/telegram-health" in page
    assert "repair_telegram_webhook" in page


def test_dashboard_contains_bulk_wallet_credit_control():
    page = render_dashboard(
        {"summary": {}, "alerts": []},
        active_tab="customers",
        dashboard_write_token="safe-write-token",
    )

    assert 'action: "bulk_credit_wallets"' in page
    assert "CREDIT ALL" in page
    assert "bulk-wallet-amount" in page


def test_dashboard_javascript_syntax_is_valid(tmp_path):
    if not shutil.which("node"):
        pytest.skip("node is not installed")

    page = render_dashboard({"summary": {}, "alerts": [], "services": []}, active_tab="catalog")
    script = re.search(r"<script>(.*?)</script>", page, flags=re.S).group(1)
    script_path = tmp_path / "dashboard.js"
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(["node", "--check", str(script_path)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
