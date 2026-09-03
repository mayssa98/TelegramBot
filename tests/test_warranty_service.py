import pytest

import database as db
from app.domain import warranty_service


def test_offer_warranty_label():
    assert warranty_service.offer_warranty_label({"warranty_days": 0}) == "NW"
    assert warranty_service.offer_warranty_label({"warranty_days": 30}) == "30 days"
    assert warranty_service.offer_warranty_label({"warranty_days": 30}, lang="fr") == "30 j"
    assert warranty_service.offer_warranty_label({"note": "NW"}) == "NW"
    assert warranty_service.offer_warranty_label({}) == "NW"
    assert warranty_service.offer_warranty_label(None) == "NW"


def test_order_warranty_label():
    assert warranty_service.order_warranty_label({"warranty_days": 0}) == "NW"
    assert warranty_service.order_warranty_label({"warranty_days": 15}) == "15 days"
    assert warranty_service.order_warranty_label({"warranty": "NW"}) == "NW"
    assert warranty_service.order_warranty_label({}) == "NW"
    assert warranty_service.order_warranty_label(None) == "NW"


def test_offer_and_order_store_period_and_warranty(mock_mongodb):
    service_id = db.add_service("Warranty products", "🛡")
    offer_id = db.add_offer(
        service_id,
        "Protected account",
        5.0,
        2,
        period_days=45,
        warranty_days=30,
    )

    offer = db.get_offer(offer_id)
    order_id = db.create_order(42, offer, 1)
    order = db.get_order(order_id)

    assert offer["period_days"] == 45
    assert offer["warranty_days"] == 30
    assert order["period_days"] == 45
    assert order["warranty_days"] == 30
    assert order["warranty"] == "30 days"


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
