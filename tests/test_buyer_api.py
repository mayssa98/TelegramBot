"""Security, wallet, delivery, and HTTP tests for the public buyer API."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

import database as db
from api.webhook import handler
from app.domain import buyer_api_service


@contextmanager
def running_server():
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _buyer_with_product(mock_mongodb, *, balance_cents=1000):
    db.upsert_user(42, "buyer", "Buyer")
    service_id = db.add_service("Accounts", "📦")
    offer_id = db.add_offer(service_id, "Premium Account", 5.0, 0)
    db.add_inventory_items(offer_id, ["user1:pass1", "user2:pass2"])
    mock_mongodb.wallets.insert_one({"user_id": 42, "balance_cents": balance_cents})
    issued = buyer_api_service.create_key(42, label="Test buyer")
    key = buyer_api_service.authenticate(issued["key"], "127.0.0.1", "balance")
    return issued, key, offer_id


def test_key_is_returned_once_but_only_hash_is_stored(mock_mongodb):
    db.upsert_user(42, "buyer", "Buyer")

    issued = buyer_api_service.create_key(42, label="Partner")
    stored = mock_mongodb.buyer_api_keys.find_one({"id": issued["id"]})

    assert issued["key"].startswith("tgb_")
    assert len(issued["key"]) == 52
    assert stored["key_hash"]
    assert "key" not in stored
    assert issued["key"] not in str(stored)
    assert issued["key"] not in str(buyer_api_service.list_keys())


def test_catalog_and_balance_are_scoped_to_key_owner(mock_mongodb):
    _issued, key, offer_id = _buyer_with_product(mock_mongodb)

    catalog = buyer_api_service.products(key)
    wallet = buyer_api_service.balance(key)

    assert catalog["success"] is True
    assert catalog["requester"]["chatId"] == 42
    assert catalog["products"][0]["_id"] == str(offer_id)
    assert catalog["products"][0]["walletPricing"] == 5.0
    assert catalog["products"][0]["stats"]["available"] == 2
    assert wallet["balance"] == 10.0
    assert wallet["walletCurrency"] == "USDT"


def test_purchase_charges_and_delivers_exactly_once(mock_mongodb):
    _issued, key, offer_id = _buyer_with_product(mock_mongodb)

    status, first, replayed = buyer_api_service.purchase(
        key,
        product_id=str(offer_id),
        quantity=1,
        idempotency_key="partner-order-001",
    )
    replay_status, second, second_replayed = buyer_api_service.purchase(
        key,
        product_id=str(offer_id),
        quantity=1,
        idempotency_key="partner-order-001",
    )

    assert status == replay_status == 200
    assert replayed is False
    assert second_replayed is True
    assert first == second
    assert first["status"] == "delivered"
    assert first["deliveredAccounts"] == ["user1:pass1"]
    assert first["balance"] == 5.0
    assert mock_mongodb.orders.count_documents({"source": "buyer_api"}) == 1
    assert mock_mongodb.inventory.count_documents({"status": "delivered"}) == 1


def test_idempotency_key_cannot_be_reused_for_another_request(mock_mongodb):
    _issued, key, offer_id = _buyer_with_product(mock_mongodb)
    buyer_api_service.purchase(
        key,
        product_id=str(offer_id),
        quantity=1,
        idempotency_key="partner-order-002",
    )

    with pytest.raises(buyer_api_service.BuyerApiError) as error:
        buyer_api_service.purchase(
            key,
            product_id=str(offer_id),
            quantity=2,
            idempotency_key="partner-order-002",
        )

    assert error.value.status == 409
    assert error.value.code == "IDEMPOTENCY_CONFLICT"


def test_insufficient_wallet_never_consumes_inventory(mock_mongodb):
    _issued, key, offer_id = _buyer_with_product(mock_mongodb, balance_cents=100)

    with pytest.raises(buyer_api_service.BuyerApiError) as error:
        buyer_api_service.purchase(
            key,
            product_id=str(offer_id),
            quantity=1,
            idempotency_key="partner-order-003",
        )

    assert error.value.code == "INSUFFICIENT_BALANCE"
    assert mock_mongodb.orders.count_documents({}) == 0
    assert mock_mongodb.inventory.count_documents({"status": "available"}) == 2
    assert mock_mongodb.wallets.find_one({"user_id": 42})["balance_cents"] == 100


def test_stock_race_refunds_wallet(monkeypatch, mock_mongodb):
    _issued, key, offer_id = _buyer_with_product(mock_mongodb)
    monkeypatch.setattr(
        "app.domain.buyer_api_service.payment_service.confirm_wallet_order",
        lambda *_args: {"status": "failed", "delivered_content": None},
    )

    with pytest.raises(buyer_api_service.BuyerApiError) as error:
        buyer_api_service.purchase(
            key,
            product_id=str(offer_id),
            quantity=1,
            idempotency_key="partner-order-race-001",
        )

    assert error.value.code == "INSUFFICIENT_STOCK"
    assert mock_mongodb.wallets.find_one({"user_id": 42})["balance_cents"] == 1000
    assert mock_mongodb.orders.find_one({"source": "buyer_api"})["status"] == "cancelled"


def test_revoked_key_is_immediately_rejected(mock_mongodb):
    issued, _key, _offer_id = _buyer_with_product(mock_mongodb)

    assert buyer_api_service.revoke_key(issued["id"]) is True
    with pytest.raises(buyer_api_service.BuyerApiError) as error:
        buyer_api_service.authenticate(issued["key"], "10.0.0.1", "products")

    assert error.value.status == 401
    assert error.value.code == "INVALID_API_KEY"


def test_endpoint_rate_limit_returns_retry_after(monkeypatch, mock_mongodb):
    issued, _key, _offer_id = _buyer_with_product(mock_mongodb)
    monkeypatch.setitem(buyer_api_service.RATE_LIMITS, "products_key", 1)

    buyer_api_service.authenticate(issued["key"], "10.0.0.2", "products")
    with pytest.raises(buyer_api_service.BuyerApiError) as error:
        buyer_api_service.authenticate(issued["key"], "10.0.0.2", "products")

    assert error.value.status == 429
    assert 1 <= error.value.retry_after <= 60


def test_swagger_and_openapi_are_public():
    with running_server() as base_url:
        with urlopen(f"{base_url}/api/swagger", timeout=5) as response:
            swagger = response.read().decode()
        with urlopen(f"{base_url}/api/openapi.json", timeout=5) as response:
            spec = json.load(response)

    assert "SwaggerUIBundle" in swagger
    assert spec["info"]["title"] == "BlackMarket Buyer API"
    assert "/api/v2/telegram-buyer/purchase" in spec["paths"]


def test_http_catalog_balance_and_idempotent_purchase(mock_mongodb):
    issued, _key, offer_id = _buyer_with_product(mock_mongodb)
    query = urlencode({"key": issued["key"]})

    with running_server() as base_url:
        with urlopen(
            f"{base_url}/api/v2/telegram-buyer/products?{query}", timeout=5
        ) as response:
            catalog = json.load(response)
        with urlopen(
            f"{base_url}/api/v2/telegram-buyer/balance?{query}", timeout=5
        ) as response:
            wallet = json.load(response)

        body = json.dumps({
            "key": issued["key"],
            "product_id": str(offer_id),
            "quantity": 1,
        }).encode()
        request = Request(
            f"{base_url}/api/v2/telegram-buyer/purchase",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": "http-partner-order-001",
            },
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            purchase = json.load(response)
            replay_header = response.headers["Idempotent-Replayed"]
        with urlopen(request, timeout=5) as response:
            replay = json.load(response)
            second_replay_header = response.headers["Idempotent-Replayed"]

    assert catalog["products"][0]["_id"] == str(offer_id)
    assert wallet["balance"] == 10.0
    assert purchase == replay
    assert replay_header == "false"
    assert second_replay_header == "true"


def test_http_invalid_key_is_safe(mock_mongodb):
    with running_server() as base_url:
        try:
            urlopen(
                f"{base_url}/api/v2/telegram-buyer/balance?key=tgb_{'0' * 48}",
                timeout=5,
            )
        except HTTPError as exc:
            payload = json.load(exc)
            assert exc.code == 401
        else:
            raise AssertionError("Invalid buyer key was accepted")

    assert payload == {
        "success": False,
        "code": "INVALID_API_KEY",
        "message": "Invalid API key.",
    }
