"""Tests unitaires pour le service d'inventaire."""

from __future__ import annotations

import database as db
from app.constants import InventoryStatus, OrderStatus
from app.domain import inventory_service


def test_add_inventory_items(mock_mongodb):
    """Vérifie l'ajout et le chiffrement d'éléments d'inventaire."""
    db.add_service("VOD", "🎬")
    offer_id = db.add_offer(service_id=1, name="Netflix 1M", price=2.99, stock=0)

    items = ["netflix1:pass123", "netflix2:pass456", "   ", "netflix1:pass123"]  # Contient un doublon et du vide
    added = inventory_service.add_items(offer_id, items)

    assert added == 2
    offer = db.get_offer(offer_id)
    assert offer["stock"] == 2

    # Vérifier que les contenus sont bien chiffrés en base et masqués
    db_items = list(mock_mongodb.inventory.find({"offer_id": offer_id}))
    assert len(db_items) == 2
    for item in db_items:
        assert isinstance(item["id"], int)
        assert item["status"] == InventoryStatus.AVAILABLE
        assert item["masked_preview"] != "netflix1:pass123"
        assert "***" in item["masked_preview"]


def test_reserve_inventory_atomic(mock_mongodb):
    """Vérifie la réservation atomique de l'inventaire."""
    db.add_service("VOD", "🎬")
    offer_id = db.add_offer(service_id=1, name="Netflix 1M", price=2.99, stock=0)
    inventory_service.add_items(offer_id, ["code1", "code2"])

    # Réserver 2 éléments
    reserved = inventory_service.reserve_for_order(offer_id, order_id=45, qty=2)
    assert reserved is not None
    assert len(reserved) == 2

    for r in reserved:
        assert r["status"] == InventoryStatus.RESERVED
        assert r["reserved_order_id"] == 45

    # Tenter une réservation supplémentaire alors que le stock est épuisé
    failed = inventory_service.reserve_for_order(offer_id, order_id=46, qty=1)
    assert failed is None


def test_reserve_rollback_on_insufficient_stock(mock_mongodb):
    """Vérifie qu'un rollback est exécuté si le stock est insuffisant pour la quantité demandée."""
    db.add_service("VOD", "🎬")
    offer_id = db.add_offer(service_id=1, name="Netflix 1M", price=2.99, stock=0)
    inventory_service.add_items(offer_id, ["code1"])

    # Demander 2 éléments alors qu'un seul est disponible
    reserved = inventory_service.reserve_for_order(offer_id, order_id=99, qty=2)
    assert reserved is None

    # L'unique élément doit être resté disponible (rollback effectué)
    db_item = mock_mongodb.inventory.find_one({"offer_id": offer_id})
    assert db_item["status"] == InventoryStatus.AVAILABLE
    assert db_item["reserved_order_id"] is None


def test_deliver_for_order(mock_mongodb):
    """Vérifie le workflow complet de livraison déchiffrée."""
    db.add_service("VOD", "🎬")
    offer_id = db.add_offer(service_id=1, name="Netflix 1M", price=2.99, stock=0)
    inventory_service.add_items(offer_id, ["netflix_cred_1234"])

    # Simuler une commande payée
    conn = db.get_conn()
    conn.orders.insert_one({
        "id": 10,
        "user_id": 12345,
        "offer_id": offer_id,
        "service_name": "VOD",
        "offer_name": "Netflix 1M",
        "qty": 1,
        "status": OrderStatus.PAID,
        "txid": "xyz",
    })

    # Effectuer la livraison
    content = inventory_service.deliver_for_order(order_id=10)
    assert content == ["netflix_cred_1234"]

    # Vérifier que le statut de l'inventaire et de la commande est mis à jour
    db_item = conn.inventory.find_one({"offer_id": offer_id})
    assert db_item["status"] == InventoryStatus.DELIVERED
    assert db_item["delivered_order_id"] == 10

    db_order = db.get_order(10)
    assert db_order["status"] == OrderStatus.DELIVERED

    # Une deuxième livraison ne révèle ni ne modifie de nouveau le contenu.
    assert inventory_service.deliver_for_order(order_id=10) is None
    assert conn.inventory.count_documents({"delivered_order_id": 10}) == 1
    assert inventory_service.delivered_content(10) == ["netflix_cred_1234"]


def test_mask_content():
    """Vérifie l'algorithme de masquage des données sensibles."""
    # Emails
    assert inventory_service.mask_content("user@gmail.com") == "us***@gmail.com"
    # Codes formattés avec tirets
    assert inventory_service.mask_content("ABCD-1234-8291") == "ABCD-****-8291"
    # Chaine courte
    assert inventory_service.mask_content("abc") == "a***"
    # Chaine standard
    assert inventory_service.mask_content("netflixpass") == "net***ss"


def test_disable_and_explicit_reveal(mock_mongodb):
    db.add_service("VOD", "🎬")
    offer_id = db.add_offer(service_id=1, name="Netflix", price=3.0, stock=0)
    inventory_service.add_items(offer_id, ["secret-value"])
    item = mock_mongodb.inventory.find_one({"offer_id": offer_id})

    assert inventory_service.set_disabled(item["id"], True) is True
    assert mock_mongodb.inventory.find_one({"id": item["id"]})["status"] == InventoryStatus.DISABLED
    assert inventory_service.reveal_item(item["id"]) == "secret-value"
    assert mock_mongodb.audit_events.count_documents({"action": "inventory.revealed"}) == 1
