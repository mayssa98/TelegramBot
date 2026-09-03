import pytest

import database as db
from app.domain import warranty_service


def test_offer_warranty_label():
    assert warranty_service.offer_warranty_label({"note": "Remplacement 24h"}) == "Remplacement 24h"
    assert warranty_service.offer_warranty_label({}) == ""
    assert warranty_service.offer_warranty_label(None) == ""


def test_order_warranty_label():
    assert warranty_service.order_warranty_label({"warranty": "Garantie 30j"}) == "Garantie 30j"
    assert warranty_service.order_warranty_label({}) == ""
    assert warranty_service.order_warranty_label(None) == ""


def test_offer_and_order_store_period_and_warranty(mock_mongodb):
    service_id = db.add_service("Warranty products", "🛡")
    offer_id = db.add_offer(
        service_id,
        "Protected account",
        5.0,
        2,
        note="Garantie complète 30 jours",
        period_days=45,
    )

    offer = db.get_offer(offer_id)
    order_id = db.create_order(42, offer, 1)
    order = db.get_order(order_id)

    assert offer["period_days"] == 45
    assert offer["note"] == "Garantie complète 30 jours"
    assert order["warranty"] == "Garantie complète 30 jours"
    assert order["period_days"] == 45


def test_legacy_warranty_migration_backfills_period_days(mock_mongodb):
    mock_mongodb.offers.insert_many([
        {"id": 1, "name": "Offer 1"},
        {"id": 2, "name": "Offer 2", "period_days": 60},
        {"id": 3, "name": "Offer 3"},
    ])

    assert db._backfill_structured_warranties(mock_mongodb) == 2
    assert mock_mongodb.offers.find_one({"id": 1})["period_days"] == 30
    assert mock_mongodb.offers.find_one({"id": 2})["period_days"] == 60
    assert mock_mongodb.offers.find_one({"id": 3})["period_days"] == 30
