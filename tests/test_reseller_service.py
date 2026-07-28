"""MailReader catalog integration and local resale configuration."""

from __future__ import annotations

import pytest

import database as db
from app.domain import reseller_service


def _supplier_payload():
    return {
        "ok": True,
        "reseller": {"name": "Demo Reseller", "balance": "42.50"},
        "products": [
            {
                "id": "mail_100",
                "name": "Mailbox 100",
                "wholesale_price": "2.25",
                "currency": "USDT",
                "description": "Automatic mailbox delivery",
                "delivery_instruction": "Use the supplied credentials",
                "stock": 12,
            },
            {
                "id": "mail_empty",
                "name": "Mailbox Empty",
                "wholesale_price": "1.00",
                "currency": "USDT",
                "stock": 0,
            },
        ],
    }


def test_catalog_overlays_admin_selection(monkeypatch, mock_mongodb):
    monkeypatch.setattr(reseller_service, "_request_json", lambda _path: _supplier_payload())
    db.save_reseller_product_config(
        "mailreader",
        "mail_100",
        name="Mailbox 100",
        wholesale_price=2.25,
        currency="USDT",
        retail_price=4.5,
        enabled=True,
    )

    result = reseller_service.catalog()

    assert result["supplier_name"] == "Demo Reseller"
    assert result["balance"] == 42.5
    assert result["selected_count"] == 1
    assert result["products"][0]["enabled"] is True
    assert result["products"][0]["retail_price"] == 4.5
    assert result["products"][0]["profit"] == 2.25
    assert result["products"][1]["enabled"] is False


def test_enabled_product_requires_profitable_retail_price(mock_mongodb):
    with pytest.raises(ValueError, match="supérieur"):
        reseller_service.save_product(
            "mail_100",
            name="Mailbox 100",
            wholesale_price=2.25,
            currency="USDT",
            retail_price=2.25,
            enabled=True,
        )


def test_api_key_is_required_without_exposing_a_secret(monkeypatch):
    monkeypatch.setattr(reseller_service, "MAILREADER_API_KEY", "")

    with pytest.raises(reseller_service.ResellerApiError, match="HP_MAILREADER_API_KEY"):
        reseller_service._request_json("/api/reseller/products")


def test_publish_product_creates_native_bot_service_and_offer(monkeypatch, mock_mongodb):
    monkeypatch.setattr(reseller_service, "_request_json", lambda _path: _supplier_payload())

    saved = reseller_service.save_catalog_product(
        "mail_100",
        retail_price=4.5,
        enabled=True,
        new_service_name="Boîtes mail",
        service_emoji="📧",
        display_name="Mailbox Premium",
        description="Livraison automatique",
        warranty="Remplacement sous 24 heures",
        delivery_delay="Instantané",
        sort_order=7,
        low_stock_threshold=3,
    )

    service = db.get_service(saved["service_id"])
    offer = db.get_offer(saved["local_offer_id"])
    assert service["name"] == "Boîtes mail"
    assert service["emoji"] == "📧"
    assert offer["name"] == "Mailbox Premium"
    assert offer["note"] == "Remplacement sous 24 heures"
    assert offer["service_id"] == service["id"]
    assert offer["supplier_provider"] == "mailreader"
    assert offer["supplier_product_id"] == "mail_100"
    assert offer["stock"] == 12
    assert offer["price"] == 4.5
    assert offer["active"] == 1
    assert offer["sort_order"] == 7
    assert saved["warranty"] == "Remplacement sous 24 heures"


def test_republishing_updates_same_native_offer(monkeypatch, mock_mongodb):
    monkeypatch.setattr(reseller_service, "_request_json", lambda _path: _supplier_payload())
    service_id = db.add_service("Emails", "📧")
    first = reseller_service.save_catalog_product(
        "mail_100", retail_price=4.5, enabled=True, service_id=service_id
    )
    second = reseller_service.save_catalog_product(
        "mail_100",
        retail_price=5.25,
        enabled=True,
        service_id=service_id,
        display_name="Mailbox Pro",
    )

    assert second["local_offer_id"] == first["local_offer_id"]
    assert mock_mongodb.offers.count_documents(
        {"supplier_provider": "mailreader", "supplier_product_id": "mail_100"}
    ) == 1
    assert db.get_offer(first["local_offer_id"])["price"] == 5.25


def test_paid_supplier_order_is_delivered_idempotently(monkeypatch, mock_mongodb):
    service_id = db.add_service("Emails", "📧")
    offer_id = db.add_offer(
        service_id,
        "Mailbox",
        4.5,
        10,
        supplier_provider="mailreader",
        supplier_product_id="mail_100",
    )
    mock_mongodb.orders.insert_one({
        "id": 91,
        "user_id": 123,
        "offer_id": offer_id,
        "qty": 2,
        "status": "payment_confirmed",
    })
    calls = []

    def fake_request(path, *, method="GET", body=None):
        calls.append((path, method, body))
        return {"order": {"id": "supplier-1"}, "delivery_items": ["user:a", "user:b"]}

    monkeypatch.setattr(reseller_service, "_request_json", fake_request)

    assert reseller_service.fulfill_paid_order(91) == ["user:a", "user:b"]
    assert reseller_service.fulfill_paid_order(91) == ["user:a", "user:b"]
    assert len(calls) == 1
    assert calls[0][1] == "POST"
    assert calls[0][2]["external_order_id"] == "BM-91"
    assert db.get_order(91)["status"] == "delivered"
    assert mock_mongodb.inventory.count_documents({"delivered_order_id": 91}) == 2
    assert "user:a" not in str(mock_mongodb.reseller_fulfillments.find_one({"order_id": 91}))
