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
