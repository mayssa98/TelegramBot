"""Service métier pour les commandes.

Centralise la logique de création, confirmation, expiration et annulation
des commandes. Les handlers Telegram appellent ces fonctions au lieu de
manipuler directement la base de données.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import database as db
from app.constants import PAID_STATUSES, TERMINAL_STATUSES, InventoryStatus, OrderStatus
from config import CURRENCY, ORDER_EXPIRY_SECONDS

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Création de commande
# ---------------------------------------------------------------------------

def check_duplicate_pending_order(user_id: int, offer_id: int) -> dict | None:
    """Renvoie une commande pending récente pour la même offre, ou None."""
    orders = db.list_user_orders(user_id, limit=10)
    for order in orders:
        if (
            order.get("offer_id") == offer_id
            and order.get("status") in (OrderStatus.PENDING_PAYMENT, OrderStatus.AWAITING_VERIFICATION)
        ):
            # Vérifier qu'elle n'est pas expirée
            expires_at = order.get("expires_at")
            if expires_at and expires_at < int(time.time()):
                expire_order(order["id"])
                continue
            return order
    return None


def create_order(user_id: int, offer: dict, qty: int = 1) -> dict:
    """Crée une commande avec expiration et renvoie l'objet complet.

    Raises:
        ValueError: si l'offre est inactive, sans prix, ou en rupture de stock.
    """
    if not offer or offer.get("price") is None or not offer.get("active", 1):
        raise ValueError("Cette offre n'est pas disponible à l'achat.")
    if offer.get("stock", 0) <= 0:
        raise ValueError("Cette offre est en rupture de stock.")
    if qty < 1:
        raise ValueError("La quantité doit être au minimum 1.")
    if qty > offer.get("stock", 0):
        raise ValueError("La quantité demandée dépasse le stock disponible.")

    now = int(time.time())
    unit_price = offer["price"]
    service = db.get_service(offer["service_id"])

    order_id = db._next_id("orders")
    order_doc: dict[str, Any] = {
        "id": order_id,
        "user_id": user_id,
        "offer_id": offer["id"],
        "service_name": service["name"] if service else "",
        "offer_name": offer["name"],
        "qty": qty,
        "unit_price": unit_price,
        "total_price": round(unit_price * qty, 2),
        "currency": CURRENCY,
        "status": OrderStatus.PENDING_PAYMENT,
        "txid": "",
        "verify_method": "",
        "delivery_text": "",
        "inventory_item_ids": [],
        "admin_note": "",
        "created_at": now,
        "expires_at": now + ORDER_EXPIRY_SECONDS,
        "paid_at": None,
        "delivered_at": None,
        "cancelled_at": None,
        "updated_at": now,
    }
    db.get_conn().orders.insert_one(order_doc)

    db.audit_event(
        "order.created",
        actor_id=user_id,
        details={"order_id": order_id, "offer_id": offer["id"], "total": order_doc["total_price"]},
    )
    log.info("Commande #%d créée pour user %d (offre %s)", order_id, user_id, offer["name"])
    return db.get_order(order_id)


# ---------------------------------------------------------------------------
# Expiration
# ---------------------------------------------------------------------------

def expire_order(order_id: int) -> bool:
    """Marque une commande comme expirée et libère l'inventaire réservé."""
    conn = db.get_conn()
    result = conn.orders.update_one(
        {
            "id": order_id,
            "status": {"$in": [OrderStatus.PENDING_PAYMENT, OrderStatus.AWAITING_VERIFICATION]},
        },
        {
            "$set": {
                "status": OrderStatus.EXPIRED,
                "cancelled_at": int(time.time()),
                "updated_at": int(time.time()),
            }
        },
    )
    if result.modified_count != 1:
        return False

    # Libérer l'inventaire réservé s'il y en a
    _release_reserved_inventory(conn, order_id)

    db.audit_event("order.expired", details={"order_id": order_id})
    log.info("Commande #%d expirée", order_id)
    return True


def expire_stale_orders() -> list[int]:
    """Expire toutes les commandes non payées dépassant le délai.

    Renvoie la liste des IDs de commandes expirées.
    """
    conn = db.get_conn()
    now = int(time.time())
    stale = list(conn.orders.find(
        {
            "status": {"$in": [OrderStatus.PENDING_PAYMENT, OrderStatus.AWAITING_VERIFICATION]},
            "expires_at": {"$lte": now, "$gt": 0},
        },
        {"id": 1},
    ))
    expired_ids = []
    for doc in stale:
        if expire_order(doc["id"]):
            expired_ids.append(doc["id"])
    return expired_ids


# ---------------------------------------------------------------------------
# Annulation
# ---------------------------------------------------------------------------

def cancel_order(order_id: int, reason: str = "") -> bool:
    """Annule manuellement une commande non terminale."""
    conn = db.get_conn()
    order = conn.orders.find_one({"id": order_id})
    if not order or order["status"] in TERMINAL_STATUSES:
        return False

    result = conn.orders.update_one(
        {"id": order_id, "status": order["status"]},
        {
            "$set": {
                "status": OrderStatus.CANCELLED,
                "cancelled_at": int(time.time()),
                "updated_at": int(time.time()),
                "admin_note": reason or order.get("admin_note", ""),
            }
        },
    )
    if result.modified_count != 1:
        return False

    # Rétablir le stock si le paiement avait été confirmé
    if order["status"] in PAID_STATUSES and order.get("offer_id"):
        conn.offers.update_one({"id": order["offer_id"]}, {"$inc": {"stock": order.get("qty", 1)}})

    _release_reserved_inventory(conn, order_id)

    db.audit_event("order.cancelled", details={"order_id": order_id, "reason": reason})
    log.info("Commande #%d annulée", order_id)
    return True


# ---------------------------------------------------------------------------
# Changement de statut
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.PENDING_PAYMENT: {OrderStatus.AWAITING_VERIFICATION, OrderStatus.CANCELLED, OrderStatus.EXPIRED},
    OrderStatus.AWAITING_VERIFICATION: {OrderStatus.PAID, OrderStatus.PAYMENT_CONFIRMED, OrderStatus.MANUAL_REVIEW, OrderStatus.VERIFICATION_FAILED, OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED, OrderStatus.EXPIRED},
    OrderStatus.VERIFICATION_FAILED: {OrderStatus.PENDING_PAYMENT, OrderStatus.MANUAL_REVIEW, OrderStatus.CANCELLED},
    OrderStatus.MANUAL_REVIEW: {OrderStatus.PAID, OrderStatus.PAYMENT_CONFIRMED, OrderStatus.CANCELLED, OrderStatus.REFUNDED},
    OrderStatus.PAID: {OrderStatus.DELIVERED, OrderStatus.PREPARING_DELIVERY, OrderStatus.CANCELLED, OrderStatus.REFUNDED},
    OrderStatus.PAYMENT_CONFIRMED: {OrderStatus.DELIVERED, OrderStatus.PREPARING_DELIVERY, OrderStatus.CANCELLED, OrderStatus.REFUNDED},
    OrderStatus.PREPARING_DELIVERY: {OrderStatus.DELIVERED, OrderStatus.CANCELLED},
    OrderStatus.DELIVERED: {OrderStatus.REFUNDED},
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
    OrderStatus.EXPIRED: set(),
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """Vérifie si une transition de statut est valide."""
    allowed = VALID_TRANSITIONS.get(from_status, set())
    return to_status in allowed


def transition_order(order_id: int, to_status: str, **extra_fields: Any) -> bool:
    """Change le statut d'une commande si la transition est valide.

    Args:
        order_id: ID de la commande.
        to_status: Nouveau statut souhaité.
        **extra_fields: Champs supplémentaires à mettre à jour.

    Returns:
        True si la transition a été effectuée.
    """
    order = db.get_order(order_id)
    if not order:
        return False

    current = order["status"]
    if not is_valid_transition(current, to_status):
        log.warning("Transition invalide: #%d %s → %s", order_id, current, to_status)
        return False

    update: dict[str, Any] = {"status": to_status, "updated_at": int(time.time())}
    if to_status in PAID_STATUSES and "paid_at" not in extra_fields:
        update["paid_at"] = int(time.time())
    if to_status == OrderStatus.DELIVERED and "delivered_at" not in extra_fields:
        update["delivered_at"] = int(time.time())

    update.update(extra_fields)
    result = db.get_conn().orders.update_one(
        {"id": order_id, "status": current},
        {"$set": update},
    )
    if result.modified_count == 1:
        db.audit_event(
            f"order.{to_status}",
            details={"order_id": order_id, "from": current, "to": to_status},
        )
        return True
    return False


def reset_for_payment(order_id: int) -> bool:
    """Return a failed/review payment to the payment waiting state."""
    conn = db.get_conn()
    result = conn.orders.update_one(
        {
            "id": order_id,
            "status": {"$in": [
                OrderStatus.AWAITING_VERIFICATION,
                OrderStatus.VERIFICATION_FAILED,
                OrderStatus.MANUAL_REVIEW,
            ]},
        },
        {
            "$set": {
                "status": OrderStatus.PENDING_PAYMENT,
                "txid": "",
                "verify_method": "",
                "updated_at": int(time.time()),
            }
        },
    )
    if result.modified_count:
        db.audit_event("order.reset_for_payment", details={"order_id": order_id})
        return True
    return False


def mark_refunded(order_id: int, reason: str = "") -> bool:
    """Mark a paid or delivered order as refunded, idempotently."""
    conn = db.get_conn()
    existing = conn.orders.find_one({"id": order_id})
    if not existing:
        return False
    if existing.get("status") == OrderStatus.REFUNDED:
        return True
    result = conn.orders.update_one(
        {
            "id": order_id,
            "status": {"$in": [
                OrderStatus.PAID,
                OrderStatus.PAYMENT_CONFIRMED,
                OrderStatus.PREPARING_DELIVERY,
                OrderStatus.DELIVERED,
                OrderStatus.MANUAL_REVIEW,
            ]},
        },
        {
            "$set": {
                "status": OrderStatus.REFUNDED,
                "refunded_at": int(time.time()),
                "admin_note": reason or existing.get("admin_note", ""),
                "updated_at": int(time.time()),
            }
        },
    )
    if result.modified_count:
        db.audit_event("order.refunded", details={"order_id": order_id, "reason": reason})
        return True
    return False


def admin_update_order(
    order_id: int,
    *,
    status: str | None = None,
    txid: str | None = None,
    qty: int | None = None,
    unit_price: float | None = None,
    total_price: float | None = None,
    admin_note: str | None = None,
) -> dict | None:
    """Update editable order fields from the admin dashboard."""
    conn = db.get_conn()
    order = conn.orders.find_one({"id": order_id})
    if not order:
        return None

    update: dict[str, Any] = {"updated_at": int(time.time())}
    if status is not None:
        valid_statuses = {item.value for item in OrderStatus}
        paid_statuses = {str(item) for item in PAID_STATUSES}
        if status not in valid_statuses:
            raise ValueError("Statut de commande invalide")
        update["status"] = status
        if status in paid_statuses and not order.get("paid_at"):
            update["paid_at"] = int(time.time())
        if status == OrderStatus.DELIVERED.value and not order.get("delivered_at"):
            update["delivered_at"] = int(time.time())
        if status == OrderStatus.CANCELLED.value and not order.get("cancelled_at"):
            update["cancelled_at"] = int(time.time())

    if txid is not None:
        txid = txid.strip()
        if txid:
            duplicate = conn.orders.find_one({"txid": txid, "id": {"$ne": order_id}}, {"id": 1})
            if duplicate:
                raise ValueError(f"TXID dÃ©jÃ  utilisÃ© par la commande #{duplicate['id']}")
        update["txid"] = txid

    if qty is not None:
        if qty < 1:
            raise ValueError("La quantitÃ© doit Ãªtre supÃ©rieure Ã  0")
        update["qty"] = qty

    if unit_price is not None:
        if unit_price < 0:
            raise ValueError("Le prix unitaire ne peut pas Ãªtre nÃ©gatif")
        update["unit_price"] = round(unit_price, 2)

    if total_price is not None:
        if total_price < 0:
            raise ValueError("Le total ne peut pas Ãªtre nÃ©gatif")
        update["total_price"] = round(total_price, 2)

    if admin_note is not None:
        update["admin_note"] = admin_note.strip()[:2000]

    conn.orders.update_one({"id": order_id}, {"$set": update})
    db.audit_event("order.admin_updated", details={"order_id": order_id, "fields": sorted(update)})
    return db.get_order(order_id)


def manual_deliver_order(order_id: int, content: str) -> dict | None:
    """Mark an order delivered with administrator-provided content."""
    content = content.strip()
    if not content:
        raise ValueError("Le contenu de livraison est obligatoire")

    conn = db.get_conn()
    result = conn.orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "status": OrderStatus.DELIVERED,
                "delivery_text": content,
                "delivered_at": int(time.time()),
                "updated_at": int(time.time()),
            }
        },
    )
    if result.matched_count != 1:
        return None
    db.audit_event("order.manual_delivered", details={"order_id": order_id})
    return db.get_order(order_id)


# ---------------------------------------------------------------------------
# Utilitaires internes
# ---------------------------------------------------------------------------

def _release_reserved_inventory(conn, order_id: int) -> int:
    """Libère tout inventaire réservé pour une commande."""
    result = conn.inventory.update_many(
        {"reserved_order_id": order_id, "status": InventoryStatus.RESERVED},
        {
            "$set": {
                "status": InventoryStatus.AVAILABLE,
                "reserved_order_id": None,
                "reserved_at": None,
            }
        },
    )
    return result.modified_count
