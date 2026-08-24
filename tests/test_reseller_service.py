"""MailReader catalog integration and local resale configuration."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest

import database as db
from app.domain import reseller_service


def _supplier_payload():
    return {
        "ok": True,
        "reseller": {"name": "Demo Reseller", "balance": "42.50"},
        "products": [
            {
                "id": "mail_100",
                "name": "Mailbox 100",
                "wholesale_price": "2.25",
                "currency": "USDT",
                "description": "Automatic mailbox delivery",
                "delivery_instruction": "Use the supplied credentials",
                "stock": 12,
            },
            {
                "id": "mail_empty",
                "name": "Mailbox Empty",
                "wholesale_price": "1.00",
                "currency": "USDT",
                "stock": 0,
            },
        ],
    }


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"delivery": ["mail:user:pass:https://mail.test/read#code"]}, ["mail:user:pass:https://mail.test/read#code"]),
        ({"result": {"items": ["shamekh:user:pass"]}}, ["shamekh:user:pass"]),
        ({"data": {"credentials": "kakao:user:pass"}}, ["kakao:user:pass"]),
        ({"data": "vex:user:pass"}, ["vex:user:pass"]),
        ({"deliveredAccounts": [{
            "user": "canboso@example.com",
            "password": "secret#1",
            "recoveryUrl": "https://canboso.test/recover?a=1&b=#code",
        }]}, [
            "canboso@example.com:secret#1:https://canboso.test/recover?a=1&b=#code",
        ]),
        ({"response": {"payload": {"delivered_accounts": ["nested:user:pass"]}}}, ["nested:user:pass"]),
        ({"delivery": {"accounts": [{
            "user": "canboso-current@example.com",
            "password": "current-secret",
            "verifyEmail": "verify@example.com",
            "expiryText": "30 days",
            "otherInfo": "keep this",
        }]}}, [
            "canboso-current@example.com:current-secret:verify@example.com:30 days:keep this",
        ]),
    ],
)
def test_delivery_extractor_supports_every_supplier_response_shape(payload, expected):
    assert reseller_service._delivery_items(payload) == expected


def test_catalog_overlays_admin_selection(monkeypatch, mock_mongodb):
    monkeypatch.setattr(reseller_service, "_request_json", lambda _path: _supplier_payload())
    db.save_reseller_product_config(
        "mailreader",
        "mail_100",
        name="Mailbox 100",
        wholesale_price=2.25,
        currency="USDT",
        retail_price=4.5,
        enabled=True,
    )

    result = reseller_service.catalog()

    assert result["supplier_name"] == "Demo Reseller"
    assert result["balance"] == 42.5
    assert result["selected_count"] == 1
    assert result["used_count"] == 1
    assert result["unused_count"] == 1
    assert result["products"][0]["enabled"] is True
    assert result["products"][0]["retail_price"] == 4.5
    assert result["products"][0]["profit"] == 2.25
    assert result["products"][1]["enabled"] is False


def test_enabled_product_requires_profitable_retail_price(mock_mongodb):
    with pytest.raises(ValueError, match="supérieur"):
        reseller_service.save_product(
            "mail_100",
            name="Mailbox 100",
            wholesale_price=2.25,
            currency="USDT",
            retail_price=2.25,
            enabled=True,
        )


def test_api_key_is_required_without_exposing_a_secret(monkeypatch):
    monkeypatch.setattr(reseller_service, "MAILREADER_API_KEY", "")

    with pytest.raises(reseller_service.ResellerApiError, match="HP_MAILREADER_API_KEY"):
        reseller_service._request_json("/api/reseller/products")


def test_canboso_key_and_idempotency_are_sent_in_documented_fields(monkeypatch):
    requests = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse({"success": True})

    monkeypatch.setattr(reseller_service, "CANBOSO_API_KEY", "test-buyer-key")
    monkeypatch.setattr(reseller_service, "GPT_CHEAP_API_KEY", "test-gpt-cheap-key")
    monkeypatch.setattr(reseller_service, "SHOP_CRON_API_KEY", "test-shop-cron-key")
    monkeypatch.setattr(
        reseller_service,
        "CANBOSO_API_BASE",
        "https://supplier.example/api/v2/telegram-buyer",
    )
    monkeypatch.setattr(reseller_service, "urlopen", fake_urlopen)

    reseller_service._canboso_request_json("/products")
    reseller_service._canboso_request_json(
        "/purchase",
        method="POST",
        body={"product_id": "sku-1", "quantity": 2},
        idempotency_key="BM-123",
    )
    reseller_service._canboso_request_json(
        "/products",
        provider=reseller_service.GPT_CHEAP_PROVIDER,
    )
    reseller_service._canboso_request_json(
        "/products",
        provider=reseller_service.SHOP_CRON_PROVIDER,
    )

    get_request, get_timeout = requests[0]
    assert get_timeout == 20
    assert parse_qs(urlsplit(get_request.full_url).query) == {"key": ["test-buyer-key"]}
    assert get_request.data is None

    post_request, post_timeout = requests[1]
    assert post_timeout == 20
    assert urlsplit(post_request.full_url).query == ""
    assert post_request.get_header("Idempotency-key") == "BM-123"
    assert json.loads(post_request.data) == {
        "key": "test-buyer-key",
        "product_id": "sku-1",
        "quantity": 2,
    }

    gpt_cheap_request, gpt_cheap_timeout = requests[2]
    assert gpt_cheap_timeout == 20
    assert parse_qs(urlsplit(gpt_cheap_request.full_url).query) == {
        "key": ["test-gpt-cheap-key"]
    }

    shop_cron_request, shop_cron_timeout = requests[3]
    assert shop_cron_timeout == 20
    assert parse_qs(urlsplit(shop_cron_request.full_url).query) == {
        "key": ["test-shop-cron-key"]
    }


def test_publish_product_creates_native_bot_service_and_offer(monkeypatch, mock_mongodb):
    monkeypatch.setattr(reseller_service, "_request_json", lambda _path: _supplier_payload())

    saved = reseller_service.save_catalog_product(
        "mail_100",
        retail_price=4.5,
        enabled=True,
        new_service_name="Boîtes mail",
        service_emoji="📧",
        display_name="Mailbox Premium",
        description="Livraison automatique",
        warranty="Remplacement sous 24 heures",
        delivery_delay="Instantané",
        sort_order=7,
        low_stock_threshold=3,
    )

    service = db.get_service(saved["service_id"])
    offer = db.get_offer(saved["local_offer_id"])
    assert service["name"] == "Boîtes mail"
    assert service["emoji"] == "📧"
    assert offer["name"] == "Mailbox Premium"
    assert offer["note"] == "Remplacement sous 24 heures"
    assert offer["service_id"] == service["id"]
    assert offer["supplier_provider"] == "mailreader"
    assert offer["supplier_product_id"] == "mail_100"
    assert offer["stock"] == 12
    assert offer["price"] == 4.5
    assert offer["active"] == 1
    assert offer["sort_order"] == 7
    assert offer["custom_emoji_id"] == ""
    assert saved["warranty"] == "Remplacement sous 24 heures"


def test_republishing_updates_same_native_offer(monkeypatch, mock_mongodb):
    monkeypatch.setattr(reseller_service, "_request_json", lambda _path: _supplier_payload())
    service_id = db.add_service("Emails", "📧")
    first = reseller_service.save_catalog_product(
        "mail_100", retail_price=4.5, enabled=True, service_id=service_id
    )
    second = reseller_service.save_catalog_product(
        "mail_100",
        retail_price=5.25,
        enabled=True,
        service_id=service_id,
        display_name="Mailbox Pro",
    )

    assert second["local_offer_id"] == first["local_offer_id"]
    assert mock_mongodb.offers.count_documents(
        {"supplier_provider": "mailreader", "supplier_product_id": "mail_100"}
    ) == 1
    assert db.get_offer(first["local_offer_id"])["price"] == 5.25


def test_paid_supplier_order_is_delivered_idempotently(monkeypatch, mock_mongodb):
    service_id = db.add_service("Emails", "📧")
    offer_id = db.add_offer(
        service_id,
        "Mailbox",
        4.5,
        10,
        supplier_provider="mailreader",
        supplier_product_id="mail_100",
    )
    mock_mongodb.orders.insert_one({
        "id": 91,
        "user_id": 123,
        "offer_id": offer_id,
        "qty": 2,
        "status": "payment_confirmed",
    })
    calls = []

    def fake_request(path, *, method="GET", body=None):
        calls.append((path, method, body))
        return {"order": {"id": "supplier-1"}, "delivery_items": ["user:a", "user:b"]}

    monkeypatch.setattr(reseller_service, "_request_json", fake_request)

    assert reseller_service.fulfill_paid_order(91) == ["user:a", "user:b"]
    assert reseller_service.fulfill_paid_order(91) == ["user:a", "user:b"]
    assert len(calls) == 1
    assert calls[0][1] == "POST"
    assert calls[0][2]["external_order_id"] == "BM-91"
    assert db.get_order(91)["status"] == "delivered"
    assert mock_mongodb.inventory.count_documents({"delivered_order_id": 91}) == 2
    assert "user:a" not in str(mock_mongodb.reseller_fulfillments.find_one({"order_id": 91}))


def test_mailreader_delivery_array_is_forwarded_without_manual_fallback(
    monkeypatch, mock_mongodb,
):
    service_id = db.add_service("Coursera", "🎓")
    offer_id = db.add_offer(
        service_id,
        "Coursera account",
        2.0,
        10,
        supplier_provider="mailreader",
        supplier_product_id="coursera-1",
    )
    mock_mongodb.orders.insert_one({
        "id": 222,
        "user_id": 123,
        "offer_id": offer_id,
        "qty": 1,
        "status": "payment_confirmed",
    })
    account = (
        "65. EloiseQuattrocchi101261@outlook.com:pasqq74516:"
        "https://www.mailreader.tech/read_code?uuid=e538cdf9-b01b-0ef4-6982-fd42c96cf98a"
    )
    monkeypatch.setattr(
        reseller_service,
        "_request_json",
        lambda *_args, **_kwargs: {
            "success": True,
            "order": {"id": "supplier-BM-222"},
            "delivery": [account],
        },
    )

    assert reseller_service.fulfill_paid_order(222) == [account]
    assert db.get_order(222)["status"] == "delivered"
    fulfillment = mock_mongodb.reseller_fulfillments.find_one({"order_id": 222})
    assert fulfillment["status"] == "completed"
    assert fulfillment["supplier_order_id"] == "supplier-BM-222"


def test_created_supplier_order_without_delivery_is_never_purchased_twice(
    monkeypatch, mock_mongodb,
):
    service_id = db.add_service("API", "🔌")
    offer_id = db.add_offer(
        service_id,
        "API account",
        2.0,
        10,
        supplier_provider="mailreader",
        supplier_product_id="api-1",
    )
    mock_mongodb.orders.insert_one({
        "id": 223,
        "user_id": 123,
        "offer_id": offer_id,
        "qty": 1,
        "status": "payment_confirmed",
    })
    calls = []

    def fake_request(*_args, **_kwargs):
        calls.append(True)
        return {"success": True, "order": {"id": "supplier-223"}, "delivery": []}

    monkeypatch.setattr(reseller_service, "_request_json", fake_request)

    with pytest.raises(reseller_service.ResellerApiError, match="pas encore disponible"):
        reseller_service.fulfill_paid_order(223)
    with pytest.raises(reseller_service.ResellerApiError, match="Aucun second achat"):
        reseller_service.fulfill_paid_order(223)

    assert len(calls) == 1
    fulfillment = mock_mongodb.reseller_fulfillments.find_one({"order_id": 223})
    assert fulfillment["status"] == "delivery_pending"
    assert fulfillment["supplier_order_id"] == "supplier-223"


def test_shamekh_catalog_maps_products_balance_and_stock(monkeypatch, mock_mongodb):
    def fake_request(path, **_kwargs):
        if path == "/api/me":
            return {"ok": True, "user": {"balance": 18.75}}
        return {
            "ok": True,
            "products": [{
                "id": 7,
                "name_en": "Premium Account",
                "price": 0.71,
                "stock_count": 97,
            }],
        }

    monkeypatch.setattr(reseller_service, "_shamekh_request_json", fake_request)

    result = reseller_service.catalog("shamekh")

    assert result["provider"] == "shamekh"
    assert result["supplier_name"] == "Shamekh’s bot"
    assert result["balance"] == 18.75
    assert result["products"][0]["id"] == "7"
    assert result["products"][0]["wholesale_price"] == 0.71
    assert result["products"][0]["stock"] == 97


def test_shamekh_product_publishes_and_delivers(monkeypatch, mock_mongodb):
    def fake_request(path, **_kwargs):
        if path == "/api/me":
            return {"ok": True, "user": {"balance": 18.75}}
        if path == "/api/buy":
            return {
                "ok": True,
                "transaction_id": "tx_supplier_1",
                "items": ["delivered-account"],
            }
        return {
            "ok": True,
            "products": [{
                "id": 7,
                "name_en": "Premium Account",
                "price": 0.71,
                "stock_count": 97,
            }],
        }

    monkeypatch.setattr(reseller_service, "_shamekh_request_json", fake_request)
    service_id = db.add_service("Premium", "⭐")
    saved = reseller_service.save_catalog_product(
        "7",
        provider="shamekh",
        retail_price=1.5,
        enabled=True,
        service_id=service_id,
        warranty="24 hours",
    )
    offer = db.get_offer(saved["local_offer_id"])
    mock_mongodb.orders.insert_one({
        "id": 92,
        "user_id": 123,
        "offer_id": offer["id"],
        "qty": 1,
        "status": "payment_confirmed",
    })

    assert offer["supplier_provider"] == "shamekh"
    assert reseller_service.fulfill_paid_order(92) == ["delivered-account"]
    fulfillment = mock_mongodb.reseller_fulfillments.find_one({"order_id": 92})
    assert fulfillment["supplier_order_id"] == "tx_supplier_1"
    assert fulfillment["status"] == "completed"
    assert db.get_order(92)["status"] == "delivered"


def test_kakao_catalog_maps_balance_source_and_products(monkeypatch, mock_mongodb):
    def fake_request(path, **_kwargs):
        if path == "/api/balance":
            return {"success": True, "balance": 62.77}
        return {
            "success": True,
            "products": [{
                "id": "kakao-1",
                "name": "Digital Account",
                "price": 1.23,
                "stock": 14,
                "source": "Kakao inventory",
            }],
        }

    monkeypatch.setattr(reseller_service, "_kakao_request_json", fake_request)

    result = reseller_service.catalog("kakao")

    assert result["provider"] == "kakao"
    assert result["supplier_name"] == "Kakao Shop"
    assert result["balance"] == 62.77
    assert result["products"][0]["id"] == "kakao-1"
    assert result["products"][0]["wholesale_price"] == 1.23
    assert result["products"][0]["stock"] == 14
    assert result["products"][0]["description"] == "Source : Kakao inventory"


def test_kakao_purchase_uses_external_id_and_is_idempotent(monkeypatch, mock_mongodb):
    calls = []

    def fake_request(path, **kwargs):
        if path == "/api/balance":
            return {"success": True, "balance": 62.77}
        if path == "/api/purchase":
            calls.append(kwargs["body"])
            return {
                "success": True,
                "order_id": 555,
                "credentials": "user:pass",
                "external_order_id": kwargs["body"]["external_order_id"],
            }
        return {
            "success": True,
            "products": [{
                "id": "kakao-1",
                "name": "Digital Account",
                "price": 1.23,
                "stock": 14,
                "source": "Kakao inventory",
            }],
        }

    monkeypatch.setattr(reseller_service, "_kakao_request_json", fake_request)
    service_id = db.add_service("Kakao", "🛍️")
    saved = reseller_service.save_catalog_product(
        "kakao-1",
        provider="kakao",
        retail_price=2.5,
        enabled=True,
        service_id=service_id,
    )
    offer = db.get_offer(saved["local_offer_id"])
    mock_mongodb.orders.insert_one({
        "id": 93,
        "user_id": 123,
        "offer_id": offer["id"],
        "qty": 1,
        "status": "payment_confirmed",
    })

    assert reseller_service.fulfill_paid_order(93) == ["user:pass"]
    assert reseller_service.fulfill_paid_order(93) == ["user:pass"]
    assert calls == [{
        "product_id": "kakao-1",
        "quantity": 1,
        "external_order_id": "BM-93",
    }]
    assert db.get_order(93)["status"] == "delivered"


def test_vex_catalog_maps_balance_stock_and_manual_delivery(monkeypatch, mock_mongodb):
    def fake_request(path, **_kwargs):
        if path == "?action=balance":
            return {"ok": True, "balance": 25.4}
        return {
            "ok": True,
            "products": [{
                "id": "5a7576cb-941f-4fb6-b56d-0a2946574650",
                "name": "VEX Account",
                "price": 0.85,
                "stock": 11,
                "manual_delivery": True,
            }],
        }

    monkeypatch.setattr(reseller_service, "_vex_request_json", fake_request)

    result = reseller_service.catalog("vex")

    assert result["provider"] == "vex"
    assert result["supplier_name"] == "VEX Reseller"
    assert result["balance"] == 25.4
    assert result["products"][0]["wholesale_price"] == 0.85
    assert result["products"][0]["stock"] == 11
    assert result["products"][0]["manual_delivery"] is True


def test_vex_order_is_delivered_and_replayed_without_double_charge(monkeypatch, mock_mongodb):
    calls = []
    product_id = "5a7576cb-941f-4fb6-b56d-0a2946574650"

    def fake_request(path, **kwargs):
        if path == "?action=balance":
            return {"ok": True, "balance": 25.4}
        if path == "?action=order":
            calls.append(kwargs["body"])
            return {
                "status": "delivered",
                "order_id": "VEX-12345678",
                "data": "vex-user:vex-pass",
                "amount": 0.85,
            }
        return {
            "ok": True,
            "products": [{
                "id": product_id,
                "name": "VEX Account",
                "price": 0.85,
                "stock": 11,
                "manual_delivery": False,
            }],
        }

    monkeypatch.setattr(reseller_service, "_vex_request_json", fake_request)
    service_id = db.add_service("VEX", "📦")
    saved = reseller_service.save_catalog_product(
        product_id,
        provider="vex",
        retail_price=1.75,
        enabled=True,
        service_id=service_id,
    )
    offer = db.get_offer(saved["local_offer_id"])
    mock_mongodb.orders.insert_one({
        "id": 94,
        "user_id": 123,
        "offer_id": offer["id"],
        "qty": 1,
        "status": "payment_confirmed",
    })

    assert offer["supplier_provider"] == "vex"
    assert reseller_service.fulfill_paid_order(94) == ["vex-user:vex-pass"]
    assert reseller_service.fulfill_paid_order(94) == ["vex-user:vex-pass"]
    assert calls == [{
        "product_id": product_id,
        "quantity": 1,
        "external_order_id": "BM-94",
    }]
    fulfillment = mock_mongodb.reseller_fulfillments.find_one({"order_id": 94})
    assert fulfillment["supplier_order_id"] == "VEX-12345678"


def test_canboso_catalog_maps_wallet_products_and_slot_delivery(monkeypatch, mock_mongodb):
    def fake_request(path, **_kwargs):
        if path == "/balance":
            return {
                "success": True,
                "walletCurrency": "VND",
                "balance": 250000,
                "usdtBalance": 0,
            }
        return {
            "success": True,
            "products": [{
                "_id": "canboso-1",
                "product_name": "ChatGPT Plus",
                "description": "Instant account",
                "usdPricing": 1.85,
                "requiresCustomerEmail": False,
                "stats": {"available": 60},
            }, {
                "_id": "canboso-slot",
                "product_name": "Business Slot",
                "usdPricing": 3.5,
                "requiresCustomerEmail": True,
                "stats": {"available": 10},
            }],
        }

    monkeypatch.setattr(reseller_service, "_canboso_request_json", fake_request)

    result = reseller_service.catalog("canboso")

    assert result["provider"] == "canboso"
    assert result["supplier_name"] == "Piggy AI"
    assert result["balance"] == 250000
    assert result["currency"] == "VND"
    assert result["products"][0]["id"] == "canboso-1"
    assert result["products"][0]["name"] == "ChatGPT Plus"
    assert result["products"][0]["wholesale_price"] == 1.85
    assert result["products"][0]["currency"] == "USDT"
    assert result["products"][0]["stock"] == 60
    assert result["products"][0]["manual_delivery"] is False
    assert result["products"][1]["manual_delivery"] is True


def test_canboso_catalog_maps_current_live_product_schema(monkeypatch, mock_mongodb):
    def fake_request(path, **_kwargs):
        if path == "/balance":
            return {
                "success": True,
                "walletCurrency": "USD",
                "balance": 12.5,
            }
        return {
            "success": True,
            "walletCurrency": "USD",
            "products": [{
                "productId": "live-account-1",
                "name": "Premium account",
                "description": "Instant account",
                "productType": "account",
                "price": {"amount": 0.05, "currency": "USD", "text": "$0.05"},
                "availability": {"available": 41, "sold": 513},
            }, {
                "productId": "live-slot-1",
                "name": "Business slot",
                "productType": "slot",
                "price": {"amount": 3.5, "currency": "USD", "text": "$3.50"},
                "availability": {"available": 10, "sold": 2},
                "purchaseRequirements": {"customerEmail": True, "quantityFixed": 1},
            }],
        }

    monkeypatch.setattr(reseller_service, "_canboso_request_json", fake_request)

    result = reseller_service.catalog("canboso")

    assert len(result["products"]) == 2
    assert result["products"][0]["id"] == "live-account-1"
    assert result["products"][0]["wholesale_price"] == 0.05
    assert result["products"][0]["currency"] == "USDT"
    assert result["products"][0]["stock"] == 41
    assert result["products"][0]["manual_delivery"] is False
    assert result["products"][1]["manual_delivery"] is True


def test_canboso_shops_use_separate_wallet_keys(monkeypatch, mock_mongodb):
    calls = []

    def fake_request(path, **kwargs):
        calls.append((path, kwargs.get("provider", "canboso")))
        if path == "/balance":
            return {"success": True, "walletCurrency": "USD", "balance": 12.5}
        return {
            "success": True,
            "products": [{
                "productId": "account-1",
                "name": "Premium account",
                "productType": "account",
                "price": {"amount": 1.0, "currency": "USD"},
                "availability": {"available": 5},
            }],
        }

    monkeypatch.setattr(reseller_service, "CANBOSO_API_KEY", "piggy-key")
    monkeypatch.setattr(reseller_service, "GPT_CHEAP_API_KEY", "gpt-cheap-key")
    monkeypatch.setattr(reseller_service, "SHOP_CRON_API_KEY", "shop-cron-key")
    monkeypatch.setattr(reseller_service, "_canboso_request_json", fake_request)

    piggy = reseller_service.catalog("canboso")
    cheap = reseller_service.catalog("gpt_cheap")
    shop_cron = reseller_service.catalog("shop_cron")

    assert piggy["supplier_name"] == "Piggy AI"
    assert cheap["supplier_name"] == "GPT Cheap"
    assert shop_cron["supplier_name"] == "Shop Cron"
    assert calls == [
        ("/products", "canboso"),
        ("/balance", "canboso"),
        ("/products", "gpt_cheap"),
        ("/balance", "gpt_cheap"),
        ("/products", "shop_cron"),
        ("/balance", "shop_cron"),
    ]


def test_canboso_purchase_uses_stable_idempotency_key(monkeypatch, mock_mongodb):
    calls = []

    def fake_request(path, **kwargs):
        calls.append((path, kwargs))
        return {
            "success": True,
            "order": {
                "orderCode": "ORDER1A2B3C4D5E",
                "status": "completed",
            },
            "delivery": {
                "accounts": [{
                    "user": "account@example.com",
                    "password": "supplier-secret",
                    "verifyEmail": "verify@example.com",
                }],
            },
        }

    monkeypatch.setattr(reseller_service, "_canboso_request_json", fake_request)
    service_id = db.add_service("Canboso", "📦")
    offer_id = db.add_offer(
        service_id,
        "Canboso Account",
        3.0,
        5,
        supplier_provider="canboso",
        supplier_product_id="canboso-1",
    )
    mock_mongodb.orders.insert_one({
        "id": 95,
        "user_id": 123,
        "offer_id": offer_id,
        "qty": 1,
        "status": "payment_confirmed",
    })

    first = reseller_service.fulfill_paid_order(95)
    second = reseller_service.fulfill_paid_order(95)

    assert first == second
    assert len(first) == 1
    assert "supplier-secret" in first[0]
    assert calls == [(
        "/purchase",
        {
            "method": "POST",
            "body": {"product_id": "canboso-1", "quantity": 1},
            "idempotency_key": "BM-95",
        },
    )]
    fulfillment = mock_mongodb.reseller_fulfillments.find_one({"order_id": 95})
    assert fulfillment["supplier_order_id"] == "ORDER1A2B3C4D5E"
    assert "supplier-secret" not in str(fulfillment)


def test_ventebot_catalog_maps_wallet_and_stock_products_only(monkeypatch, mock_mongodb):
    def fake_request(path, **_kwargs):
        if path == "/api/reseller/me":
            return {"success": True, "wallet_balance": 31.25}
        return {
            "success": True,
            "products": [{
                "id": 12,
                "name": "Stock account",
                "description": "Instant credentials",
                "price_usd": 1.4,
                "delivery_type": "stock",
                "stock": 9,
                "api_test": False,
            }, {
                "id": 13,
                "name": "Activation service",
                "price_usd": 2.0,
                "delivery_type": "activation",
                "stock": None,
                "api_test": False,
            }, {
                "id": 99,
                "name": "API test",
                "price_usd": 0.01,
                "delivery_type": "api_test",
                "stock": 999,
                "api_test": True,
            }],
        }

    monkeypatch.setattr(reseller_service, "_ventebot_request_json", fake_request)

    result = reseller_service.catalog("ventebot")

    assert result["provider"] == "ventebot"
    assert result["supplier_name"] == "VenteBot"
    assert result["balance"] == 31.25
    assert [product["id"] for product in result["products"]] == ["12"]
    assert result["products"][0]["wholesale_price"] == 1.4
    assert result["products"][0]["stock"] == 9


def test_ventebot_purchase_is_idempotent_and_extracts_account_data(
    monkeypatch, mock_mongodb,
):
    calls = []

    def fake_request(path, **kwargs):
        calls.append((path, kwargs))
        return {
            "success": True,
            "order": {
                "id": 812,
                "status": "COMPLETED",
                "items": [{"id": 1, "account_data": "user:password"}],
            },
        }

    monkeypatch.setattr(reseller_service, "_ventebot_request_json", fake_request)
    offer_id = db.add_offer(
        db.add_service("VenteBot", "📦"),
        "Stock account",
        2.5,
        5,
        supplier_provider="ventebot",
        supplier_product_id="12",
    )
    mock_mongodb.orders.insert_one({
        "id": 96,
        "user_id": 123,
        "offer_id": offer_id,
        "qty": 1,
        "status": "payment_confirmed",
    })

    assert reseller_service.fulfill_paid_order(96) == ["user:password"]
    assert reseller_service.fulfill_paid_order(96) == ["user:password"]
    assert calls == [(
        "/api/reseller/orders",
        {
            "method": "POST",
            "body": {
                "product_id": 12,
                "quantity": 1,
                "customer_reference": "telegram_user_123",
                "idempotency_key": "BM-96",
            },
        },
    )]
    assert db.get_order(96)["status"] == "delivered"


def test_restock_detection_baselines_then_reports_only_increases(monkeypatch, mock_mongodb):
    offer_id = db.add_offer(
        service_id=db.add_service("API stock", "📦"),
        name="API plan",
        price=9.0,
        stock=0,
        supplier_provider="mailreader",
        supplier_product_id="sku-1",
    )
    db.save_reseller_product_config(
        "mailreader",
        "sku-1",
        name="API plan",
        wholesale_price=5.0,
        currency="USDT",
        retail_price=9.0,
        enabled=True,
        service_id=1,
        local_offer_id=offer_id,
    )
    stock = {"value": 2}

    def fake_catalog(provider):
        assert provider == "mailreader"
        db.update_offer(offer_id, stock=stock["value"])
        return {
            "products": [{
                "id": "sku-1",
                "enabled": True,
                "local_offer_id": offer_id,
                "stock": stock["value"],
            }]
        }

    monkeypatch.setattr(reseller_service, "MAILREADER_API_KEY", "configured")
    monkeypatch.setattr(reseller_service, "SHAMEKH_API_KEY", "")
    monkeypatch.setattr(reseller_service, "KAKAO_API_KEY", "")
    monkeypatch.setattr(reseller_service, "VEX_API_KEY", "")
    monkeypatch.setattr(reseller_service, "CANBOSO_API_KEY", "")
    monkeypatch.setattr(reseller_service, "GPT_CHEAP_API_KEY", "")
    monkeypatch.setattr(reseller_service, "SHOP_CRON_API_KEY", "")
    monkeypatch.setattr(reseller_service, "VENTEBOT_API_KEY", "")
    monkeypatch.setattr(reseller_service, "catalog", fake_catalog)

    assert reseller_service.detect_restock_events()["events"] == []
    stock["value"] = 6
    result = reseller_service.detect_restock_events()
    assert result["events"] == [{
        "provider": "mailreader",
        "product_id": "sku-1",
        "offer_id": offer_id,
        "previous_stock": 2,
        "stock": 6,
        "added": 4,
    }]
    assert reseller_service.detect_restock_events()["events"] == []


def test_supplier_price_drop_preserves_markup_and_creates_flash_event(
    monkeypatch, mock_mongodb,
):
    service_id = db.add_service("API prices", "🔥")
    offer_id = db.add_offer(
        service_id, "API plan", 15.0, 8,
        supplier_provider="mailreader", supplier_product_id="sku-price",
    )
    db.save_reseller_product_config(
        "mailreader",
        "sku-price",
        name="API plan",
        wholesale_price=10.0,
        currency="USDT",
        retail_price=15.0,
        enabled=True,
        service_id=service_id,
        local_offer_id=offer_id,
    )
    wholesale = {"value": 10.0}

    monkeypatch.setattr(reseller_service, "MAILREADER_API_KEY", "configured")
    monkeypatch.setattr(reseller_service, "SHAMEKH_API_KEY", "")
    monkeypatch.setattr(reseller_service, "KAKAO_API_KEY", "")
    monkeypatch.setattr(reseller_service, "VEX_API_KEY", "")
    monkeypatch.setattr(reseller_service, "CANBOSO_API_KEY", "")
    monkeypatch.setattr(reseller_service, "GPT_CHEAP_API_KEY", "")
    monkeypatch.setattr(reseller_service, "SHOP_CRON_API_KEY", "")
    monkeypatch.setattr(reseller_service, "VENTEBOT_API_KEY", "")
    monkeypatch.setattr(
        reseller_service,
        "catalog",
        lambda _provider: {
            "products": [{
                "id": "sku-price",
                "enabled": True,
                "local_offer_id": offer_id,
                "wholesale_price": wholesale["value"],
            }]
        },
    )

    assert reseller_service.detect_supplier_price_changes()["changes"] == []
    wholesale["value"] = 8.0
    result = reseller_service.detect_supplier_price_changes()

    assert len(result["flash_sales"]) == 1
    assert result["flash_sales"][0]["markup_percent"] == 50.0
    assert result["flash_sales"][0]["previous_price"] == 15.0
    assert result["flash_sales"][0]["price"] == 12.0
    assert db.get_offer(offer_id)["price"] == 12.0
