"""Tests unitaires pour le service des commandes."""

from __future__ import annotations

import time
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


def test_expire_order(mock_mongodb):
    """Vérifie le marquage de commande expirée."""
    db.add_service("Discord", "🎮")
    offer_id = db.add_offer(service_id=1, name="Nitro", price=9.99, stock=5)
    offer = db.get_offer(offer_id)

    order = order_service.create_order(user_id=12345, offer=offer, qty=1)
    assert order_service.expire_order(order["id"]) is True

    updated_order = db.get_order(order["id"])
    assert updated_order["status"] == OrderStatus.EXPIRED


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
