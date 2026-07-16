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
