import pytest

import database as db
from app.domain import warranty_service


def test_fw_warranty_validates_one_to_365_days():
    assert warranty_service.normalize_warranty("fw", 1) == ("FW", 1)
    assert warranty_service.normalize_warranty("FW", "365") == ("FW", 365)
    with pytest.raises(ValueError):
        warranty_service.normalize_warranty("FW", 0)
    with pytest.raises(ValueError):
        warranty_service.normalize_warranty("FW", 366)


def test_nw_disables_the_warranty_timer():
    assert warranty_service.normalize_warranty("NW", 120) == ("NW", 0)
    assert warranty_service.warranty_label("NW", 0) == "NW · No warranty"


def test_order_keeps_a_fixed_warranty_option_without_monitoring_time():
    order = {"warranty_type": "FW", "warranty_days": 30, "delivered_at": 1_000}

    assert warranty_service.order_warranty_label(order) == "FW · 30 days"


def test_offer_and_order_store_structured_warranty(mock_mongodb):
    service_id = db.add_service("Warranty products", "🛡")
    offer_id = db.add_offer(
        service_id,
        "Protected account",
        5.0,
        2,
        warranty_type="FW",
        warranty_days=45,
    )

    offer = db.get_offer(offer_id)
    order_id = db.create_order(42, offer, 1)
    order = db.get_order(order_id)

    assert offer["warranty_type"] == "FW"
    assert offer["warranty_days"] == 45
    assert offer["note"] == "FW · 45 days"
    assert order["warranty"] == "FW · 45 days"
    assert order["warranty_type"] == "FW"
    assert order["warranty_days"] == 45


def test_legacy_warranty_migration_only_structures_recognized_notes(mock_mongodb):
    mock_mongodb.offers.insert_many([
        {"id": 1, "note": "Garantie 25 jours"},
        {"id": 2, "note": "NW"},
        {"id": 3, "note": "Contact support for details"},
    ])

    assert db._backfill_structured_warranties(mock_mongodb) == 2
    assert mock_mongodb.offers.find_one({"id": 1})["warranty_days"] == 25
    assert mock_mongodb.offers.find_one({"id": 2})["warranty_type"] == "NW"
    assert "warranty_type" not in mock_mongodb.offers.find_one({"id": 3})
