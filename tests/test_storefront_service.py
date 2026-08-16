"""Tunisia storefront catalog and manual-payment order tests."""

from __future__ import annotations

import base64

import pytest

import database as db
from app.domain import inventory_service, storefront_service


def _product() -> int:
    service_id = db.add_service("AI", "✨")
    return db.add_offer(
        service_id,
        "ChatGPT Plus",
        10,
        2,
        description="Compte premium",
    )


def _payload(offer_id: int) -> dict:
    return {
        "name": "Client Tunisien",
        "phone": "+216 26 183 573",
        "email": "client@example.com",
        "offer_id": offer_id,
        "quantity": 1,
        "payment_method": "d17",
        "transaction_reference": "D17-REF-123",
        "proof": {
            "name": "recu.png",
            "type": "image/png",
            "data": base64.b64encode(b"\x89PNG\r\n\x1a\nproof").decode(),
        },
    }


def test_catalog_projects_existing_bot_products_in_tnd(mock_mongodb, monkeypatch):
    monkeypatch.setattr(storefront_service, "TN_TND_PER_USDT", "3.2")
    offer_id = _product()

    result = storefront_service.catalog("fr")

    product = result["services"][0]["products"][0]
    assert product["id"] == offer_id
    assert product["currency"] == "TND"
    assert product["price_millimes"] == 32_000
    assert product["available"] is True
    assert product["category"] == "ai"
    assert product["logo_url"] == "https://cdn.simpleicons.org/openai/FFFFFF"
    assert result["categories"] == [{"id": "ai", "label": "Outils IA"}]


def test_unknown_service_uses_local_generated_logo(mock_mongodb):
    service_id = db.add_service("Service interne", "◆")
    db.add_offer(service_id, "Accès spécial", 2, 1)

    product = storefront_service.catalog("fr")["services"][0]["products"][0]

    assert product["logo_url"] == "/storefront/service-fallback.png"


def test_catalog_uses_site_visual_content_and_cleans_telegram_markup(mock_mongodb):
    offer_id = _product()
    db.update_offer(
        offer_id,
        description="[[HTML]]<b>Description bot</b><tg-emoji emoji-id=\"1\">⚡</tg-emoji>",
        site_description_fr="Une description claire pour le site.",
        site_description_ar="وصف واضح للموقع",
        site_image_url="https://cdn.example.com/chatgpt.webp",
        site_category="ai",
        site_badge="Populaire",
        site_badge_ar="الأكثر طلباً",
        site_featured=True,
    )

    french = storefront_service.catalog("fr")["services"][0]["products"][0]
    arabic = storefront_service.catalog("ar")["services"][0]["products"][0]

    assert french["description"] == "Une description claire pour le site."
    assert french["image_url"] == "https://cdn.example.com/chatgpt.webp"
    assert french["badge"] == "Populaire"
    assert french["featured"] is True
    assert arabic["description"] == "وصف واضح للموقع"
    assert arabic["badge"] == "الأكثر طلباً"


def test_storefront_order_requires_tunisian_phone_and_encrypts_receipt(mock_mongodb):
    offer_id = _product()
    payload = _payload(offer_id)

    created = storefront_service.create_order(payload)

    row = mock_mongodb.site_orders.find_one({"id": created["order_id"]})
    proof = mock_mongodb.storefront_payment_proofs.find_one({"order_id": created["order_id"]})
    assert row["phone"] == "+21626183573"
    assert row["status"] == "manual_review"
    assert row["total_millimes"] == 32_000
    assert "proof" not in str(row)
    assert "encrypted_payload" in proof
    assert storefront_service.order_status(created["order_id"], created["tracking_token"])["order"]["status"] == "manual_review"


def test_storefront_rejects_non_tunisian_phone_and_duplicate_reference(mock_mongodb):
    offer_id = _product()
    payload = _payload(offer_id)
    storefront_service.create_order(payload)

    with pytest.raises(storefront_service.StorefrontError, match="déjà été utilisée"):
        storefront_service.create_order(payload)

    invalid = _payload(offer_id)
    invalid["phone"] = "+33 6 12 34 56 78"
    invalid["transaction_reference"] = "OTHER-REF"
    with pytest.raises(storefront_service.StorefrontError, match="tunisien"):
        storefront_service.create_order(invalid)


def test_site_visibility_can_exclude_a_bot_product(mock_mongodb):
    offer_id = _product()
    mock_mongodb.offers.update_one(
        {"id": offer_id},
        {"$set": {"sales_channels": ["bot"]}},
    )

    assert storefront_service.catalog("fr")["services"] == []


def test_admin_approval_delivers_inventory_once(mock_mongodb):
    offer_id = _product()
    inventory_service.add_items(offer_id, ["login@example.com\nSecret-123"])
    created = storefront_service.create_order(_payload(offer_id))

    result = storefront_service.review_order(
        created["order_id"], approved=True, admin_id=999,
    )

    assert result["status"] == "delivered"
    tracked = storefront_service.order_status(
        created["order_id"], created["tracking_token"],
    )["order"]
    assert tracked["delivery"] == ["login@example.com\nSecret-123"]
    with pytest.raises(storefront_service.StorefrontError, match="déjà été traitée"):
        storefront_service.review_order(created["order_id"], approved=True, admin_id=999)


def test_admin_can_reject_manual_payment(mock_mongodb):
    created = storefront_service.create_order(_payload(_product()))

    result = storefront_service.review_order(
        created["order_id"], approved=False, admin_id=999, reason="Référence introuvable",
    )

    assert result["status"] == "rejected"
    tracked = storefront_service.order_status(
        created["order_id"], created["tracking_token"],
    )["order"]
    assert tracked["rejection_reason"] == "Référence introuvable"
