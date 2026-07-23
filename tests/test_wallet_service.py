"""Tests for verified wallet top-ups and balance usage."""

import pytest

import database as db
from app.domain import order_service, payment_service, wallet_service


def test_verified_topup_credits_real_transfer_amount(mock_mongodb, monkeypatch):
    monkeypatch.setattr(wallet_service, "verify_incoming_transfer", lambda *_args, **_kwargs: {
        "status": "confirmed", "amount": 12.5, "currency": "USDT",
    })

    result = wallet_service.claim_transfer(42, "TXID_TOPUP_123")

    assert result["status"] == "confirmed"
    assert result["amount"] == 12.5
    assert result["balance"] == 12.5


def test_topup_txid_cannot_be_used_twice(mock_mongodb, monkeypatch):
    monkeypatch.setattr(wallet_service, "verify_incoming_transfer", lambda *_args, **_kwargs: {
        "status": "confirmed", "amount": 5.0, "currency": "USDT",
    })
    assert wallet_service.claim_transfer(42, "TXID_UNIQUE_123")["status"] == "confirmed"
    assert wallet_service.claim_transfer(99, "TXID_UNIQUE_123")["code"] == "already_used"


def test_wallet_pays_order_and_reduces_external_total(mock_mongodb):
    db.add_service("AI", "🤖")
    offer_id = db.add_offer(1, "Premium", 10.0, 1)
    mock_mongodb.wallets.insert_one({"user_id": 42, "balance_cents": 1000})

    order = order_service.create_order(42, db.get_offer(offer_id), payment_method="wallet")

    assert order["wallet_amount"] == 10.0
    assert order["total_price"] == 0.0
    assert wallet_service.balance_cents(42) == 0


def test_partial_wallet_balance_reduces_amount_left_for_binance(mock_mongodb):
    db.add_service("AI", "T")
    offer_id = db.add_offer(1, "Premium", 10.0, 1)
    mock_mongodb.wallets.insert_one({"user_id": 42, "balance_cents": 300})

    order = order_service.create_order(
        42, db.get_offer(offer_id), payment_method="wallet"
    )

    assert order["wallet_amount"] == 3.0
    assert order["total_price"] == 7.0
    assert order["payment_method"] == "wallet_binance"
    assert wallet_service.balance_cents(42) == 0


def test_wallet_button_rejects_an_empty_balance(mock_mongodb):
    db.add_service("AI", "T")
    offer_id = db.add_offer(1, "Premium", 10.0, 1)

    with pytest.raises(ValueError, match="0.00 USDT"):
        order_service.create_order(
            42, db.get_offer(offer_id), payment_method="wallet"
        )


def test_full_wallet_payment_confirms_and_delivers(mock_mongodb):
    db.add_service("AI", "T")
    offer_id = db.add_offer(1, "Premium", 10.0, 0)
    db.add_inventory_items(offer_id, ["delivered_from_wallet"])
    mock_mongodb.wallets.insert_one({"user_id": 42, "balance_cents": 1000})
    order = order_service.create_order(
        42, db.get_offer(offer_id), payment_method="wallet"
    )

    result = payment_service.confirm_wallet_order(order["id"], 42)

    assert result["status"] == "delivered"
    assert result["delivered_content"] == ["delivered_from_wallet"]
    assert db.get_order(order["id"])["verify_method"] == "wallet"


def test_automatic_topup_credits_transfer_matched_by_optional_memo(mock_mongodb, monkeypatch):
    monkeypatch.setattr(wallet_service, "verify_incoming_transfer_by_memo", lambda *_args, **_kwargs: {
        "status": "confirmed",
        "txid": "AUTO_MEMO_TX_123",
        "amount": 7.5,
        "currency": "USDT",
    })

    result = wallet_service.claim_transfer_by_memo(42, 1_700_000_000)

    assert result["status"] == "confirmed"
    assert result["amount"] == 7.5
    assert wallet_service.balance_cents(42) == 750
    assert mock_mongodb.wallet_topups.find_one({"txid": "AUTO_MEMO_TX_123"})["verification_method"] == "memo"
