"""Tests unitaires pour le service des paiements."""

from __future__ import annotations

import pytest

import database as db
from app.constants import OrderStatus
from app.domain import order_service, payment_service


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
    """Vérifie le flux de paiement réussi avec un TXID Binance."""
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


def test_txid_verification_uses_receipt_id_and_amount(mock_mongodb, monkeypatch):
    captured = {}

    def verifier(txid, amount, currency=None, created_at=None):
        captured.update({
            "txid": txid,
            "amount": amount,
        })
        return {"status": "confirmed", "reason": "confirmed"}

    monkeypatch.setattr(payment_service, "verify_payment", verifier)
    db.add_service("VOD", "T")
    offer_id = db.add_offer(service_id=1, name="Netflix", price=5.0, stock=1)
    db.add_inventory_items(offer_id, ["delivery"])
    db.get_conn().orders.insert_one({
        "id": 12, "user_id": 123, "offer_id": offer_id,
        "service_name": "VOD", "offer_name": "Netflix", "qty": 1,
        "total_price": 5.0, "status": OrderStatus.PENDING_PAYMENT,
        "txid": "", "created_at": 100, "expires_at": 9999999999,
    })

    result = payment_service.submit_payment(12, "BINANCE_TX_123", 123)

    assert result["status"] == "delivered"
    assert captured == {
        "txid": "BINANCE_TX_123",
        "amount": 5.0,
    }


def test_bybit_order_uses_bybit_verifier(mock_mongodb, monkeypatch):
    captured = {}

    def bybit_verifier(txid, amount, currency=None, created_at=None):
        captured.update({"txid": txid, "amount": amount, "currency": currency})
        return {"status": "confirmed", "reason": "confirmed"}

    monkeypatch.setattr(payment_service, "verify_bybit_payment", bybit_verifier)
    monkeypatch.setattr(
        payment_service,
        "verify_payment",
        lambda *_args, **_kwargs: pytest.fail("Binance verifier was called"),
    )
    db.add_service("AI", "T")
    offer_id = db.add_offer(service_id=1, name="Lovable", price=12.0, stock=1)
    db.add_inventory_items(offer_id, ["delivery"])
    db.get_conn().orders.insert_one({
        "id": 13, "user_id": 123, "offer_id": offer_id,
        "service_name": "AI", "offer_name": "Lovable", "qty": 1,
        "total_price": 12.0, "payment_method": "bybit",
        "status": OrderStatus.PENDING_PAYMENT, "txid": "",
        "created_at": 100, "expires_at": 9999999999,
    })

    result = payment_service.submit_payment(13, "BYBIT_TX_123", 123)

    assert result["status"] == "delivered"
    assert captured == {"txid": "BYBIT_TX_123", "amount": 12.0, "currency": "USDT"}
    assert db.get_order(13)["verify_method"] == "bybit_txid"


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
    db.add_service("Manual", "M")
    offer_id = db.add_offer(service_id=1, name="Manual product", price=5.0, stock=1)
    conn = db.get_conn()
    conn.orders.insert_one({
        "id": 1,
        "user_id": 123,
        "offer_id": offer_id,
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


def test_temporary_verifier_error_never_enters_manual_review(mock_mongodb, monkeypatch):
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

    assert result["status"] == "failed"
    order = db.get_order(20)
    assert order["status"] == OrderStatus.PENDING_PAYMENT
    assert order["txid"] == ""


def test_confirmed_payment_qualifies_pending_referral_once(mock_mongodb, mock_payment_verifier):
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
        "total_price": 10.0,
        "status": OrderStatus.PENDING_PAYMENT,
        "txid": "",
    })

    result = payment_service.submit_payment(30, "TXID_QUALIFIED", 111)

    assert result["affiliate"]["valid_referrals"] == 1
    assert result["affiliate"]["rewarded"] is False
    assert mock_mongodb.referrals.find_one({"referred_id": 111})["valid"] is True
    assert affiliate_service.on_confirmed_payment(111, 30) is None


def test_admin_test_payment_bypasses_binance_and_delivers(mock_mongodb, monkeypatch):
    import time

    monkeypatch.setattr(payment_service, "ADMIN_ID", 999)
    db.set_setting("admin_test_payment_enabled", "true")
    db.add_service("Test", "🧪")
    offer_id = db.add_offer(1, "Test product", 5.0, 1)
    db.add_inventory_items(offer_id, ["test_delivery_content"])
    stock_before = db.get_offer(offer_id)["stock"]
    db.get_conn().orders.insert_one({
        "id": 40, "user_id": 999, "offer_id": offer_id,
        "service_name": "Test", "offer_name": "Test product",
        "qty": 1, "total_price": 5.0,
        "status": OrderStatus.PENDING_PAYMENT, "txid": "",
        "created_at": int(time.time()), "expires_at": int(time.time()) + 1800,
    })

    result = payment_service.submit_payment(40, "TEST-PAYMENT", 999)

    assert result["status"] == "delivered"
    assert result["delivered_content"] == [
        "SAMPLE TEST PRODUCT 1/1 — NOT A REAL PRODUCT — ORDER #40",
    ]
    assert db.get_order(40)["verify_method"] == "admin_test"
    assert db.inventory_stats(offer_id)["available"] == 1
    assert db.get_offer(offer_id)["stock"] == stock_before


def test_admin_test_payment_can_be_enabled_by_environment_config(
    mock_mongodb, monkeypatch
):
    import time

    monkeypatch.setattr(payment_service, "ADMIN_ID", 999)
    monkeypatch.setattr(payment_service, "TEST_PAYMENT_ENABLED", True)
    db.add_service("Test", "T")
    offer_id = db.add_offer(1, "Test product", 5.0, 1)
    db.add_inventory_items(offer_id, ["real_inventory_must_remain_available"])
    stock_before = db.get_offer(offer_id)["stock"]
    db.get_conn().orders.insert_one({
        "id": 42, "user_id": 999, "offer_id": offer_id,
        "service_name": "Test", "offer_name": "Test product",
        "qty": 1, "total_price": 5.0,
        "status": OrderStatus.PENDING_PAYMENT, "txid": "",
        "created_at": int(time.time()), "expires_at": int(time.time()) + 1800,
    })

    result = payment_service.submit_payment(42, "TEST-PAYMENT", 999)

    assert result["status"] == "delivered"
    assert db.get_order(42)["verify_method"] == "admin_test"
    assert db.get_offer(offer_id)["stock"] == stock_before
    assert db.inventory_stats(offer_id)["available"] == 1


def test_customer_cannot_use_admin_test_payment(mock_mongodb, monkeypatch):
    import time

    monkeypatch.setattr(payment_service, "ADMIN_ID", 999)
    db.set_setting("admin_test_payment_enabled", "true")
    db.get_conn().orders.insert_one({
        "id": 41, "user_id": 123, "offer_id": 1, "qty": 1,
        "total_price": 5.0, "status": OrderStatus.PENDING_PAYMENT,
        "txid": "", "created_at": int(time.time()),
        "expires_at": int(time.time()) + 1800,
    })

    result = payment_service.submit_payment(41, "TEST-PAYMENT", 123)

    assert result["status"] == "failed"
    assert result["error_code"] == "not_found"
    assert db.get_order(41)["status"] == OrderStatus.PENDING_PAYMENT
def test_onchain_payment_is_saved_for_manual_review(mock_mongodb):
    service_id = db.add_service("VPN", "🔒")
    offer_id = db.add_offer(service_id, "VPN plan", 5.0, 2)
    order = order_service.create_order(
        42, db.get_offer(offer_id), payment_method="usdt_bsc",
    )
    txid = "0x" + "a" * 64

    result = payment_service.submit_onchain_payment(order["id"], txid, 42)

    saved = db.get_order(order["id"])
    assert result["status"] == "manual_review"
    assert result["network"] == "BSC (BEP20)"
    assert saved["status"] == OrderStatus.MANUAL_REVIEW
    assert saved["txid"] == txid
    assert saved["verify_method"] == "manual_usdt_bsc"


def test_admin_approval_finalizes_onchain_order_exactly_once(mock_mongodb):
    service_id = db.add_service("VPN", "T")
    offer_id = db.add_offer(service_id, "VPN plan", 5.0, 1)
    db.add_inventory_items(offer_id, ["vpn-account"])
    order = order_service.create_order(
        42, db.get_offer(offer_id), payment_method="usdt_polygon",
    )
    payment_service.submit_onchain_payment(order["id"], "0x" + "b" * 64, 42)

    result = payment_service.review_onchain_payment(
        order["id"], 999, approved=True,
    )
    repeated = payment_service.review_onchain_payment(
        order["id"], 999, approved=True,
    )

    assert result["status"] == "delivered"
    assert result["delivered_content"] == ["vpn-account"]
    assert result["order"]["verify_method"] == "approved_usdt_polygon"
    assert result["order"]["reviewed_by"] == 999
    assert repeated["status"] == "already_processed"


def test_admin_rejection_returns_onchain_order_to_failed_verification(mock_mongodb):
    service_id = db.add_service("VPN", "T")
    offer_id = db.add_offer(service_id, "VPN plan", 5.0, 1)
    order = order_service.create_order(
        42, db.get_offer(offer_id), payment_method="usdt_bsc",
    )
    txid = "0x" + "c" * 64
    payment_service.submit_onchain_payment(order["id"], txid, 42)

    result = payment_service.review_onchain_payment(
        order["id"], 999, approved=False,
    )
    repeated = payment_service.review_onchain_payment(
        order["id"], 999, approved=False,
    )

    assert result["status"] == "rejected"
    assert result["order"]["status"] == OrderStatus.VERIFICATION_FAILED
    assert result["order"]["verify_method"] == "rejected_usdt_bsc"
    assert result["order"]["txid"] == txid
    assert repeated["status"] == "already_processed"
