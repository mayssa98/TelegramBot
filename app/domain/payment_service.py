"""Service métier pour les paiements.

Centralise la validation du TXID, la vérification automatique, l'idempotence
et le passage en revue manuelle.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import database as db
from app.constants import OrderStatus
from app.domain import affiliate_service, inventory_service, loyalty_service
from config import CURRENCY
from payment_verifier import verify_payment, verify_payment_by_amount

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation du TXID
# ---------------------------------------------------------------------------

class TxidValidationError(Exception):
    """Erreur de validation du TXID avec un code d'erreur structuré."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def validate_txid_format(txid: str) -> str:
    """Valide et nettoie un TXID.

    Raises:
        TxidValidationError: si le format est invalide.
    """
    txid = txid.strip()

    if len(txid) < 6:
        raise TxidValidationError("too_short", "Le TXID est trop court (minimum 6 caractères).")

    if len(txid) > 128:
        raise TxidValidationError("too_long", "Le TXID est trop long (maximum 128 caractères).")

    if not re.fullmatch(r"[A-Za-z0-9_-]+", txid):
        raise TxidValidationError("invalid_chars", "Le TXID contient des caractères non autorisés.")

    return txid


def check_txid_uniqueness(txid: str, order_id: int) -> None:
    """Vérifie qu'un TXID n'a pas déjà été utilisé par une autre commande.

    Raises:
        TxidValidationError: si le TXID est déjà associé à une autre commande.
    """
    conn = db.get_conn()
    existing = conn.orders.find_one(
        {"txid": txid, "id": {"$ne": order_id}},
    )
    if existing:
        raise TxidValidationError(
            "already_used",
            f"Ce TXID a déjà été utilisé pour la commande #{existing['id']}.",
        )


def _finalize_confirmed_payment(order_id: int, user_id: int, txid: str, method: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "failed",
        "order": db.get_order(order_id),
        "delivered_content": None,
        "error_code": None,
        "error_message": None,
        "affiliate": None,
    }
    if txid:
        db.update_order(order_id, txid=txid)
    if db.mark_order_paid(order_id, method):
        result["status"] = "confirmed"
        result["affiliate"] = affiliate_service.on_confirmed_payment(user_id, order_id)
        result["loyalty"] = loyalty_service.record_purchase(user_id)
        delivered = inventory_service.deliver_for_order(order_id)
        if delivered:
            result["delivered_content"] = delivered
            result["status"] = "delivered"
        else:
            result["status"] = "confirmed_no_delivery"
        db.audit_event(
            "payment.confirmed",
            actor_id=user_id,
            details={"order_id": order_id, "txid": txid, "method": method},
        )
    else:
        result["error_code"] = "payment_failed"
        result["error_message"] = "Le paiement n'a pas pu etre enregistre (stock insuffisant ou erreur)."
    return result


def confirm_wallet_order(order_id: int, user_id: int) -> dict[str, Any]:
    order = db.get_order(order_id)
    if not order or order.get("user_id") != user_id or float(order.get("total_price", 1)) != 0:
        return {"status": "failed", "order": order, "delivered_content": None, "affiliate": None}
    return _finalize_confirmed_payment(order_id, user_id, "", "wallet")


# ---------------------------------------------------------------------------
# Workflow de paiement
# ---------------------------------------------------------------------------

def submit_payment(order_id: int, txid: str, user_id: int) -> dict[str, Any]:
    """Soumet un TXID pour vérification.

    Workflow complet :
    1. Valider le format du TXID
    2. Vérifier l'unicité
    3. Vérifier la propriété de la commande
    4. Vérifier que la commande est dans un état acceptable
    5. Lancer la vérification automatique
    6. Livrer si confirmé, ou passer en revue manuelle

    Returns:
        dict avec les clés: status, order, delivered_content, error_code, error_message
    """
    result: dict[str, Any] = {
        "status": "failed",
        "order": None,
        "delivered_content": None,
        "error_code": None,
        "error_message": None,
        "affiliate": None,
    }

    # 1. Valider le format
    try:
        txid = validate_txid_format(txid)
    except TxidValidationError as exc:
        result["error_code"] = exc.code
        result["error_message"] = exc.message
        return result

    # 2. Récupérer et vérifier la commande
    order = db.get_order(order_id)
    if not order:
        result["error_code"] = "order_not_found"
        result["error_message"] = "Commande introuvable."
        return result

    result["order"] = order

    if order["user_id"] != user_id:
        result["error_code"] = "not_owner"
        result["error_message"] = "Cette commande ne vous appartient pas."
        return result

    # Vérifier que la commande n'est pas déjà payée/livrée
    if order["status"] in (OrderStatus.PAID, OrderStatus.PAYMENT_CONFIRMED, OrderStatus.DELIVERED):
        result["error_code"] = "already_paid"
        result["error_message"] = "Cette commande a déjà été payée."
        result["status"] = "already_paid"
        return result

    # Vérifier que la commande est dans un état de paiement
    if order["status"] not in (OrderStatus.PENDING_PAYMENT, OrderStatus.AWAITING_VERIFICATION, OrderStatus.VERIFICATION_FAILED):
        result["error_code"] = "invalid_status"
        result["error_message"] = f"La commande est en statut {order['status']} et ne peut pas recevoir de paiement."
        return result

    # Vérifier expiration
    if order.get("expires_at") and order["expires_at"] < int(time.time()):
        from app.domain.order_service import expire_order
        expire_order(order_id)
        result["error_code"] = "expired"
        result["error_message"] = "Cette commande a expiré. Veuillez en créer une nouvelle."
        return result

    # 3. Vérifier unicité du TXID
    try:
        check_txid_uniqueness(txid, order_id)
    except TxidValidationError as exc:
        result["error_code"] = exc.code
        result["error_message"] = exc.message
        return result

    # 4. Enregistrer le TXID et passer en vérification
    db.update_order(order_id, txid=txid, status=OrderStatus.AWAITING_VERIFICATION)

    # 5. Vérification automatique
    verification = verify_payment(
        txid, order["total_price"], CURRENCY, order.get("created_at"), expected_memo=user_id
    )

    if verification["status"] == "confirmed":
        result.update(_finalize_confirmed_payment(order_id, user_id, txid, "auto_txid"))
    elif verification["status"] == "manual_review":
        reason = verification.get("reason", "Vérification automatique indisponible")
        db.update_order(
            order_id,
            status=OrderStatus.PENDING_PAYMENT,
            txid="",
            verify_method="auto_unavailable",
        )
        result["status"] = "failed"
        result["error_code"] = verification.get("code", "temporary_error")
        result["error_message"] = reason
        db.audit_event(
            "payment.verification_unavailable",
            actor_id=user_id,
            details={"order_id": order_id, "reason": reason},
        )
    else:
        # Vérification échouée
        reason = verification.get("reason", "Raison inconnue")
        db.update_order(
            order_id,
            status=OrderStatus.PENDING_PAYMENT,
            txid="",
            verify_method="auto_failed",
        )
        result["error_code"] = verification.get("code", "verification_failed")
        result["error_message"] = reason

        db.audit_event(
            "payment.verification_failed",
            actor_id=user_id,
            details={"order_id": order_id, "txid": txid, "reason": reason},
        )

    return result


def auto_check_payment(order_id: int, user_id: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "failed",
        "order": None,
        "delivered_content": None,
        "error_code": None,
        "error_message": None,
        "affiliate": None,
    }
    order = db.get_order(order_id)
    if not order:
        result["error_code"] = "order_not_found"
        result["error_message"] = "Commande introuvable."
        return result
    result["order"] = order
    if order["user_id"] != user_id:
        result["error_code"] = "not_owner"
        result["error_message"] = "Cette commande ne vous appartient pas."
        return result
    if order["status"] in (OrderStatus.PAID, OrderStatus.PAYMENT_CONFIRMED, OrderStatus.DELIVERED):
        result["status"] = "already_paid"
        return result
    if order["status"] not in (OrderStatus.PENDING_PAYMENT, OrderStatus.AWAITING_VERIFICATION, OrderStatus.VERIFICATION_FAILED):
        result["error_code"] = "invalid_status"
        result["error_message"] = f"La commande est en statut {order['status']} et ne peut pas recevoir de paiement."
        return result
    if order.get("expires_at") and order["expires_at"] < int(time.time()):
        from app.domain.order_service import expire_order
        expire_order(order_id)
        result["error_code"] = "expired"
        result["error_message"] = "Cette commande a expire. Veuillez en creer une nouvelle."
        return result

    used_txids = [
        item.get("txid")
        for item in db.get_conn().orders.find({"txid": {"$nin": ["", None]}, "id": {"$ne": order_id}}, {"txid": 1})
    ]
    verification = verify_payment_by_amount(
        order["total_price"], CURRENCY, order.get("created_at"),
        used_txids=used_txids, expected_memo=user_id,
    )
    if verification["status"] == "confirmed":
        txid = verification.get("txid", "")
        try:
            if txid:
                check_txid_uniqueness(txid, order_id)
        except TxidValidationError as exc:
            result["error_code"] = exc.code
            result["error_message"] = exc.message
            return result
        result.update(_finalize_confirmed_payment(order_id, user_id, txid, "auto_amount"))
    elif verification["status"] == "manual_review":
        result["status"] = "failed"
        result["error_code"] = verification.get("code", "temporary_error")
        result["error_message"] = verification.get("reason", "Verification automatique indisponible")
    else:
        result["error_code"] = verification.get("code", "not_found")
        result["error_message"] = verification.get("reason", "Aucun paiement exact recent detecte")
    return result


# ---------------------------------------------------------------------------
# Confirmation manuelle (admin)
# ---------------------------------------------------------------------------

def confirm_payment_manual(order_id: int) -> bool:
    """Confirme manuellement le paiement d'une commande.

    Idempotent : ne fait rien si la commande est déjà payée.
    """
    order = db.get_order(order_id)
    if not order:
        return False

    if order["status"] in (OrderStatus.PAID, OrderStatus.PAYMENT_CONFIRMED, OrderStatus.DELIVERED):
        log.info("Commande #%d déjà confirmée, confirmation manuelle ignorée", order_id)
        return True  # idempotent

    if db.mark_order_paid(order_id, "manual"):
        db.audit_event(
            "payment.confirmed_manual",
            details={"order_id": order_id},
        )
        return True
    return False


def mark_manual_review(order_id: int, reason: str = "") -> bool:
    """Place une commande en revue manuelle."""
    conn = db.get_conn()
    result = conn.orders.update_one(
        {
            "id": order_id,
            "status": {"$in": [
                OrderStatus.AWAITING_VERIFICATION,
                OrderStatus.VERIFICATION_FAILED,
                OrderStatus.PENDING_PAYMENT,
            ]},
        },
        {
            "$set": {
                "status": OrderStatus.MANUAL_REVIEW,
                "admin_note": reason,
                "updated_at": int(time.time()),
            }
        },
    )
    if result.modified_count:
        db.audit_event("payment.manual_review", details={"order_id": order_id, "reason": reason})
        return True
    return False
