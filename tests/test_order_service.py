"""Tests unitaires pour le service des commandes."""

from __future__ import annotations

import pytest

import database as db
from app.constants import OrderStatus
from app.domain import order_service


def test_create_order_success(mock_mongodb):
    """Vérifie la création réussie d'une commande."""
    # Créer un service et une offre valides
    db.add_service("Discord", "🎮")
    offer_id = db.add_offer(service_id=1, name="Nitro 1 Year", price=9.99, stock=5)
    offer = db.get_offer(offer_id)

    # Créer la commande
    order = order_service.create_order(user_id=12345, offer=offer, qty=1)

    assert order["id"] == 1
    assert order["user_id"] == 12345
    assert order["offer_id"] == offer_id
    assert order["unit_price"] == 9.99
    assert order["total_price"] == 9.99
    assert order["status"] == OrderStatus.PENDING_PAYMENT
    assert order["expires_at"] > order["created_at"]


def test_catalog_persists_admin_selected_custom_emoji(mock_mongodb):
    service_id = db.add_service("Streaming", custom_emoji_id="service-premium-id")
    offer_id = db.add_offer(
        service_id,
        "Premium",
        5.0,
        2,
        custom_emoji_id="offer-premium-id",
    )

    assert db.get_service(service_id)["custom_emoji_id"] == "service-premium-id"
    assert db.get_offer(offer_id)["custom_emoji_id"] == "offer-premium-id"


def test_offer_persists_publicity_image_and_calculates_sales(mock_mongodb):
    offer_id = db.add_offer(
        service_id=1,
        name="Premium",
        price=4.99,
        stock=0,
        photo_file_id="telegram-photo-id",
        description="Premium account",
        instructions="Do not change the recovery email",
    )
    offer = db.get_offer(offer_id)
    assert offer["photo_file_id"] == "telegram-photo-id"
    assert offer["description"] == "Premium account"
    assert offer["instructions"] == "Do not change the recovery email"

    mock_mongodb.orders.insert_many([
        {"id": 1001, "offer_id": offer_id, "qty": 2, "status": "delivered"},
        {"id": 1002, "offer_id": offer_id, "qty": 1, "status": "payment_confirmed"},
        {"id": 1003, "offer_id": offer_id, "qty": 5, "status": "cancelled"},
    ])
    assert db.offer_sold_count(offer_id) == 3


def test_create_order_inactive_offer(mock_mongodb):
    """Vérifie qu'on ne peut pas commander une offre inactive."""
    db.add_service("Discord", "🎮")
    offer_id = db.add_offer(service_id=1, name="Nitro 1 Year", price=9.99, stock=5)
    db.update_offer(offer_id, active=0)
    offer = db.get_offer(offer_id)

    with pytest.raises(ValueError, match="Cette offre n'est pas disponible"):
        order_service.create_order(user_id=12345, offer=offer, qty=1)


def test_create_order_out_of_stock(mock_mongodb):
    """Vérifie qu'on ne peut pas commander une offre en rupture de stock."""
    db.add_service("Discord", "🎮")
    offer_id = db.add_offer(service_id=1, name="Nitro 1 Year", price=9.99, stock=0)
    offer = db.get_offer(offer_id)

    with pytest.raises(ValueError, match="rupture de stock"):
        order_service.create_order(user_id=12345, offer=offer, qty=1)


def test_create_order_rejects_quantity_above_stock(mock_mongodb):
    db.add_service("Discord", "🎮")
    offer_id = db.add_offer(service_id=1, name="Nitro 1 Year", price=9.99, stock=2)
    offer = db.get_offer(offer_id)

    with pytest.raises(ValueError, match="stock disponible"):
        order_service.create_order(user_id=12345, offer=offer, qty=3)


def test_check_duplicate_pending_order(mock_mongodb):
    """Vérifie la détection de commandes en cours dupliquées."""
    db.add_service("Discord", "🎮")
    offer_id = db.add_offer(service_id=1, name="Nitro", price=9.99, stock=5)
    offer = db.get_offer(offer_id)

    # Aucune commande en cours au début
    assert order_service.check_duplicate_pending_order(12345, offer_id) is None

    # Créer une commande
    order_service.create_order(user_id=12345, offer=offer, qty=1)

    # Détection de la commande dupliquée
    dup = order_service.check_duplicate_pending_order(12345, offer_id)
    assert dup is not None
    assert dup["id"] == 1


def test_new_order_cancels_older_incomplete_orders(mock_mongodb):
    db.add_service("Discord", "🎮")
    offer_id = db.add_offer(service_id=1, name="Nitro", price=9.99, stock=5)
    offer = db.get_offer(offer_id)
    old_order = order_service.create_order(user_id=12345, offer=offer, qty=1)
    new_order = order_service.create_order(user_id=12345, offer=offer, qty=2)

    cancelled = order_service.cancel_incomplete_orders(12345, exclude_order_id=new_order["id"])

    assert cancelled == [old_order["id"]]
    assert db.get_order(old_order["id"])["status"] == OrderStatus.CANCELLED
    assert db.get_order(new_order["id"])["status"] == OrderStatus.PENDING_PAYMENT


def test_expire_order(mock_mongodb):
    """Vérifie le marquage de commande expirée."""
    db.add_service("Discord", "🎮")
    offer_id = db.add_offer(service_id=1, name="Nitro", price=9.99, stock=5)
    offer = db.get_offer(offer_id)

    order = order_service.create_order(user_id=12345, offer=offer, qty=1)
    assert order_service.expire_order(order["id"]) is True

    updated_order = db.get_order(order["id"])
    assert updated_order["status"] == OrderStatus.EXPIRED


def test_expire_order_releases_reserved_inventory(mock_mongodb):
    """Expiring an order releases inventory using the canonical reservation field."""
    db.add_service("VOD", "🎬")
    offer_id = db.add_offer(service_id=1, name="Netflix", price=5.0, stock=0)
    from app.domain import inventory_service

    inventory_service.add_items(offer_id, ["credential"])
    offer = db.get_offer(offer_id)
    order = order_service.create_order(user_id=12345, offer=offer, qty=1)
    assert inventory_service.reserve_for_order(offer_id, order["id"], 1)

    assert order_service.expire_order(order["id"]) is True

    item = mock_mongodb.inventory.find_one({"offer_id": offer_id})
    assert item["status"] == "available"
    assert item["reserved_order_id"] is None


def test_transition_order(mock_mongodb):
    """Vérifie la validation des transitions de statut d'une commande."""
    db.add_service("Discord", "🎮")
    offer_id = db.add_offer(service_id=1, name="Nitro", price=9.99, stock=5)
    offer = db.get_offer(offer_id)

    order = order_service.create_order(user_id=12345, offer=offer, qty=1)
    oid = order["id"]

    # Transition valide : pending_payment -> awaiting_verification
    assert order_service.transition_order(oid, OrderStatus.AWAITING_VERIFICATION) is True

    # Transition invalide : awaiting_verification -> delivered (doit passer par paid d'abord)
    assert order_service.transition_order(oid, OrderStatus.DELIVERED) is False

    # Transition valide : awaiting_verification -> payment_confirmed
    assert order_service.transition_order(oid, OrderStatus.PAYMENT_CONFIRMED) is True


def test_reset_for_payment_and_refund(mock_mongodb):
    conn = db.get_conn()
    conn.orders.insert_one({"id": 50, "status": OrderStatus.MANUAL_REVIEW, "txid": "TX123456"})
    assert order_service.reset_for_payment(50) is True
    reset = db.get_order(50)
    assert reset["status"] == OrderStatus.PENDING_PAYMENT
    assert reset["txid"] == ""

    conn.orders.update_one({"id": 50}, {"$set": {"status": OrderStatus.DELIVERED}})
    assert order_service.mark_refunded(50, "Customer request") is True
    assert order_service.mark_refunded(50, "Customer request") is True
    assert db.get_order(50)["status"] == OrderStatus.REFUNDED


def test_admin_update_order_fields(mock_mongodb):
    conn = db.get_conn()
    conn.orders.insert_one({
        "id": 77,
        "status": OrderStatus.PENDING_PAYMENT,
        "txid": "",
        "qty": 1,
        "unit_price": 10.0,
        "total_price": 10.0,
    })

    updated = order_service.admin_update_order(
        77,
        status=OrderStatus.MANUAL_REVIEW,
        txid="TX-ADMIN-77",
        qty=2,
        unit_price=8.5,
        total_price=17.0,
        admin_note="Needs manual review",
    )

    assert updated is not None
    assert updated["status"] == OrderStatus.MANUAL_REVIEW
    assert updated["txid"] == "TX-ADMIN-77"
    assert updated["qty"] == 2
    assert updated["unit_price"] == 8.5
    assert updated["total_price"] == 17.0
    assert updated["admin_note"] == "Needs manual review"


def test_manual_deliver_order(mock_mongodb):
    conn = db.get_conn()
    conn.orders.insert_one({
        "id": 78,
        "user_id": 123,
        "status": OrderStatus.PAYMENT_CONFIRMED,
        "delivery_text": "",
    })

    delivered = order_service.manual_deliver_order(78, "account:password")

    assert delivered is not None
    assert delivered["status"] == OrderStatus.DELIVERED
    assert delivered["delivery_text"] == "account:password"
    assert delivered["delivered_at"]
