"""Regression tests for paid-order announcements."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import database as db
from admin import post_purchase_to_channel


def test_wallet_purchase_announcement_displays_real_product_total(mock_mongodb):
    service_id = db.add_service("Lovable", "🛍")
    offer_id = db.add_offer(service_id, "Lovable Pro Lite Account 12m", 12.0, 1)
    bot = SimpleNamespace(
        get_me=AsyncMock(return_value=SimpleNamespace(username="blackmarket_bot")),
        send_message=AsyncMock(),
    )
    order = {
        "offer_id": offer_id,
        "service_id": service_id,
        "service_name": "Lovable",
        "offer_name": "Lovable Pro Lite Account 12m",
        "qty": 1,
        "unit_price": 12.0,
        "gross_total": 12.0,
        "wallet_amount": 12.0,
        "total_price": 0.0,
    }

    asyncio.run(post_purchase_to_channel(SimpleNamespace(bot=bot), order))

    message = bot.send_message.await_args.kwargs["text"]
    assert "Total Price:</b> <code>$12.00 USDT" in message
    assert "$0.00 USDT" not in message


def test_preorder_uses_a_dedicated_channel_announcement(mock_mongodb):
    service_id = db.add_service("ChatGPT", "🤖")
    offer_id = db.add_offer(service_id, "Plus 1 month", 10.0, 0)
    bot = SimpleNamespace(
        get_me=AsyncMock(return_value=SimpleNamespace(username="blackmarket_bot")),
        send_message=AsyncMock(),
    )
    order = {
        "offer_id": offer_id,
        "service_id": service_id,
        "service_name": "ChatGPT",
        "offer_name": "Plus 1 month",
        "qty": 2,
        "unit_price": 11.0,
        "gross_total": 22.0,
        "total_price": 22.0,
        "is_preorder": True,
    }

    asyncio.run(post_purchase_to_channel(SimpleNamespace(bot=bot), order))

    call = bot.send_message.await_args.kwargs
    assert "NEW PRE-ORDER CONFIRMED" in call["text"]
    assert "Quantity Pre-ordered" in call["text"]
    assert "Pre-order Total:</b> <code>$22.00 USDT" in call["text"]
    assert "Awaiting Restock" in call["text"]
    assert "NEW ORDER COMPLETED" not in call["text"]
    assert call["reply_markup"].inline_keyboard[0][0].text == "⏳ Pre-order Now"
