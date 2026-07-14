"""Tests unitaires pour le service des paiements."""

from __future__ import annotations

import pytest

import database as db
from app.constants import OrderStatus
from app.domain import payment_service


@pytest.fixture
def mock_payment_verifier(monkeypatch):
    """Permet d'injecter une réponse simulée de verify_payment."""
    state = {"status": "confirmed", "reason": "Transaction Binance Pay confirmée"}

    def _mock(txid, amount, currency=None, created_at=None):
        return state

    monkeypatch.setattr(payment_service, "verify_payment", _mock)
    return state


def test_validate_txid_format():
    """Vérifie le filtrage de format de transaction (TXID)."""
    # Valides
    assert payment_service.validate_txid_format("123456") == "123456"
    assert payment_service.validate_txid_format("TXID-993-abc_123") == "TXID-993-abc_123"

    # Trop court
    with pytest.raises(payment_service.TxidValidationError, match="trop court"):
        payment_service.validate_txid_format("12345")

    # Caractères interdits
    with pytest.raises(payment_service.TxidValidationError, match="caractères non autorisés"):
        payment_service.validate_txid_format("TXID@123")


def test_submit_payment_success(mock_mongodb, mock_payment_verifier):
    """Vérifie le flux de paiement réussi avec vérification automatique."""
    db.add_service("VOD", "🎬")
    offer_id = db.add_offer(service_id=1, name="Netflix", price=5.0, stock=3)

    # Ajouter du stock pour permettre la livraison automatique
    db.add_inventory_items(offer_id, ["code_netflix_123"])

    # Créer une commande
    import time
    now = int(time.time())
    conn = db.get_conn()
    conn.orders.insert_one({
        "id": 1,
        "user_id": 123,
        "offer_id": offer_id,
        "service_name": "VOD",
        "offer_name": "Netflix",
        "qty": 1,
        "total_price": 5.0,
        "status": OrderStatus.PENDING_PAYMENT,
        "txid": "",
        "created_at": now - 60,
        "expires_at": now + 1800,
    })

    # Soumettre le paiement
    result = payment_service.submit_payment(order_id=1, txid="TXID_VALID_123", user_id=123)

    assert result["status"] == "delivered"
    assert result["delivered_content"] == ["code_netflix_123"]

    db_order = db.get_order(1)
    assert db_order["status"] == OrderStatus.DELIVERED
    assert db_order["txid"] == "TXID_VALID_123"


def test_auto_check_payment_by_exact_amount_delivers(mock_mongodb, monkeypatch):
    db.add_service("VOD", "🎬")
    offer_id = db.add_offer(service_id=1, name="Netflix", price=5.0, stock=3)
    db.add_inventory_items(offer_id, ["code_netflix_auto"])
    conn = db.get_conn()
    conn.orders.insert_one({
        "id": 11,
        "user_id": 123,
        "offer_id": offer_id,
        "service_name": "VOD",
        "offer_name": "Netflix",
        "qty": 1,
        "total_price": 5.0,
        "status": OrderStatus.PENDING_PAYMENT,
        "txid": "",
        "created_at": 100,
        "expires_at": 9999999999,
    })
    monkeypatch.setattr(
        payment_service,
        "verify_payment_by_amount",
        lambda *args, **kwargs: {"status": "confirmed", "txid": "AUTO_TX_123456"},
    )

    result = payment_service.auto_check_payment(11, 123)

    assert result["status"] == "delivered"
    assert result["delivered_content"] == ["code_netflix_auto"]
    order = db.get_order(11)
    assert order["status"] == OrderStatus.DELIVERED
    assert order["txid"] == "AUTO_TX_123456"


def test_submit_payment_duplicate_txid(mock_mongodb):
    """Vérifie qu'on ne peut pas réutiliser le même TXID pour une autre commande."""
    conn = db.get_conn()
    # Commande 1 déjà payée avec le TXID
    conn.orders.insert_one({
        "id": 1,
        "user_id": 123,
        "status": OrderStatus.DELIVERED,
        "txid": "TXID_DEJA_UTILISE",
    })
    # Commande 2 en attente
    conn.orders.insert_one({
        "id": 2,
        "user_id": 123,
        "status": OrderStatus.PENDING_PAYMENT,
        "txid": "",
        "total_price": 5.0,
    })

    # Tenter de réutiliser le TXID
    result = payment_service.submit_payment(order_id=2, txid="TXID_DEJA_UTILISE", user_id=123)
    assert result["status"] == "failed"
    assert result["error_code"] == "already_used"


def test_confirm_payment_manual(mock_mongodb):
    """Vérifie l'idempotence et la confirmation manuelle par l'admin."""
    conn = db.get_conn()
    conn.orders.insert_one({
        "id": 1,
        "user_id": 123,
        "offer_id": 1,
        "qty": 1,
        "total_price": 5.0,
        "status": OrderStatus.PENDING_PAYMENT,
        "txid": "",
    })

    # Confirmer manuellement
    assert payment_service.confirm_payment_manual(order_id=1) is True

    db_order = db.get_order(1)
    assert db_order["status"] in (OrderStatus.PAID, OrderStatus.PAYMENT_CONFIRMED)

    # Ré-essayer (idempotent, doit renvoyer True)
    assert payment_service.confirm_payment_manual(order_id=1) is True


def test_confirm_payment_from_manual_review(mock_mongodb):
    """An administrator can confirm an order explicitly placed in manual review."""
    conn = db.get_conn()
    conn.orders.insert_one({
        "id": 7,
        "user_id": 123,
        "qty": 1,
        "total_price": 5.0,
        "status": OrderStatus.MANUAL_REVIEW,
        "txid": "REVIEW_123",
    })

    assert payment_service.confirm_payment_manual(order_id=7) is True
    assert db.get_order(7)["status"] == OrderStatus.PAYMENT_CONFIRMED


def test_temporary_verifier_error_enters_manual_review(mock_mongodb, monkeypatch):
    conn = db.get_conn()
    conn.orders.insert_one({
        "id": 20,
        "user_id": 123,
        "total_price": 5.0,
        "status": OrderStatus.PENDING_PAYMENT,
        "txid": "",
    })
    monkeypatch.setattr(
        payment_service,
        "verify_payment",
        lambda *args, **kwargs: {"status": "manual_review", "code": "temporary_error", "reason": "timeout"},
    )

    result = payment_service.submit_payment(20, "TXID_123456", 123)

    assert result["status"] == "manual_review"
    order = db.get_order(20)
    assert order["status"] == OrderStatus.MANUAL_REVIEW
    assert order["txid"] == "TXID_123456"


def test_payment_qualifies_referral_only_after_confirmation(mock_mongodb, mock_payment_verifier):
    from app.domain import affiliate_service

    mock_mongodb.users.insert_many([{"telegram_id": 999}, {"telegram_id": 111}])
    assert affiliate_service.register_referral_link(111, 999) is True
    offer_id = db.add_offer(1, "Digital", 5.0, 1)
    conn = db.get_conn()
    conn.orders.insert_one({
        "id": 30,
        "user_id": 111,
        "offer_id": offer_id,
        "qty": 1,
        "total_price": 5.0,
        "status": OrderStatus.PENDING_PAYMENT,
        "txid": "",
    })

    result = payment_service.submit_payment(30, "TXID_QUALIFIED", 111)

    assert result["affiliate"]["referrer_id"] == 999
    assert mock_mongodb.referrals.find_one({"referred_id": 111})["first_payment"] is True
