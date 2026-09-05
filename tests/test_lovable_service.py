"""Lovable Unlimited Credit storefront and license regressions."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.request import Request, urlopen

import database as db
import keyboards as kb
from app.domain import lovable_service
from bot import deliver_order, send_payment_result
from tests.test_webhook_http import running_server


def test_dedicated_lovable_plans_have_fixed_prices_and_stay_out_of_catalog(mock_mongodb):
    db._delete_lovable_catalog(mock_mongodb)
    assert not any(
        offer.get("feature_key") == "lovable_unlimited"
        for offer in db.list_catalog_offers()
    )
    assert not any(
        s.get("feature_key") == "lovable_unlimited"
        for s in db.list_services(active_only=False)
    )


def test_lovable_moves_from_home_into_shop_and_keeps_dedicated_buy_buttons(mock_mongodb):
    home = kb.home_keyboard("en", 42)
    home_callbacks = [button.callback_data for row in home.inline_keyboard for button in row]
    shop = kb.catalog_offers_keyboard("en")
    shop_callbacks = [button.callback_data for row in shop.inline_keyboard for button in row]
    assert "lovable" not in home_callbacks
    assert "lovable" not in shop_callbacks


def test_free_trial_is_limited_to_one_manual_request_per_user(mock_mongodb):
    first, created_first = lovable_service.request_trial(42)
    second, created_second = lovable_service.request_trial(42)

    assert (created_first, created_second) == (True, False)
    assert first["id"] == second["id"]
    assert first["status"] == "pending"
    assert mock_mongodb.lovable_licenses.count_documents({}) == 0


def test_paid_lovable_order_waits_for_admin_then_registers_manual_license(
    monkeypatch, mock_mongodb,
):
    mock_mongodb.offers.insert_one({
        "id": 888,
        "name": "7 Days Access",
        "duration_days": 7,
        "feature_key": "lovable_unlimited",
    })
    mock_mongodb.orders.insert_one({
        "id": 801,
        "user_id": 42,
        "offer_id": 888,
        "service_name": "Lovable Unlimited Credit",
        "offer_name": "7 Days Access",
        "status": "payment_confirmed",
    })
    notify_manual = AsyncMock()
    monkeypatch.setattr("bot.admin.notify_manual_delivery_request", notify_manual)
    message = SimpleNamespace(reply_text=AsyncMock())
    bot_client = SimpleNamespace(send_message=AsyncMock(), send_document=AsyncMock())

    asyncio.run(send_payment_result(
        message,
        SimpleNamespace(bot=bot_client),
        "en",
        801,
        {
            "status": "confirmed_no_delivery",
            "affiliate": None,
            "loyalty": None,
            "delivered_content": None,
        },
        42,
    ))

    assert db.get_order(801)["status"] == "payment_confirmed"
    assert mock_mongodb.lovable_licenses.count_documents({}) == 0
    notify_manual.assert_awaited_once()

    admin_reply = SimpleNamespace(reply_text=AsyncMock())
    asyncio.run(deliver_order(
        SimpleNamespace(message=admin_reply),
        SimpleNamespace(bot=bot_client),
        801,
        "MANUAL-LOVABLE-LICENSE-801",
    ))

    assert db.get_order(801)["status"] == "delivered"
    assert lovable_service.validate_license("MANUAL-LOVABLE-LICENSE-801")["valid"] is True


def test_extension_zip_is_configurable_by_telegram_file_id(mock_mongodb):
    saved = lovable_service.set_extension_file("telegram-zip-file", "lovable-v1.zip")

    assert saved == {
        "file_id": "telegram-zip-file",
        "file_name": "lovable-v1.zip",
    }


def test_public_extension_endpoint_validates_license_with_cors(mock_mongodb):
    lovable_service.request_trial(73)
    lovable_service.complete_trial(73, "MANUAL-TRIAL-LICENSE-73")
    request = Request(
        "http://placeholder/api/lovable/license/validate",
        data=json.dumps({"license": "MANUAL-TRIAL-LICENSE-73"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with running_server() as base_url:
        request.full_url = f"{base_url}/api/lovable/license/validate"
        with urlopen(request, timeout=5) as response:
            payload = json.load(response)

    assert payload["valid"] is True
    assert response.headers["Access-Control-Allow-Origin"] == "*"
