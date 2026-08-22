import database as db


def test_services_with_stock_returns_totals_without_n_plus_one(mock_mongodb):
    first = db.add_service("First", "1")
    second = db.add_service("Second", "2")
    db.add_offer(first, "A", 1.0, 2)
    db.add_offer(first, "B", 1.0, 3)
    db.add_offer(second, "C", 1.0, 1)

    services = db.list_services_with_stock()
    totals = {service["id"]: service["total_stock"] for service in services}

    assert totals[first] == 5
    assert totals[second] == 1


def test_flat_catalog_returns_offers_from_active_services_only(mock_mongodb):
    active = db.add_service("Active", "A")
    inactive = db.add_service("Inactive", "I")
    visible = db.add_offer(active, "Visible offer", 2.0, 4)
    hidden = db.add_offer(inactive, "Hidden offer", 3.0, 5)
    db.update_service(inactive, active=0)

    offers = db.list_catalog_offers()

    assert [offer["id"] for offer in offers] == [visible]
    assert offers[0]["service_name"] == "Active"
    assert hidden not in {offer["id"] for offer in offers}


def test_catalog_propagates_service_button_suffix(mock_mongodb):
    service_id = db.add_service(
        "officiels subscribes", "⭐", suffix_emoji="✅",
    )
    db.add_offer(service_id, "Premium", 5.0, 4)

    service = db.get_service(service_id)
    offer = db.list_catalog_offers()[0]

    assert service["suffix_emoji"] == "✅"
    assert offer["service_suffix_emoji"] == "✅"
