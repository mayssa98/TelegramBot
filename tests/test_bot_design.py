"""Regression tests for the customer-facing Telegram navigation."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import keyboards as kb
from bot import cb_navigation, order_service_groups, orders_text_export, payment_scanner_frame
from i18n import t


def test_main_menu_is_compact_and_actions_match_labels():
    keyboard = kb.main_menu_keyboard("fr", user_id=42)

    labels = [[button.text for button in row] for row in keyboard.keyboard[:3]]
    assert labels == [
        [t("fr", "menu_catalog"), t("fr", "menu_orders")],
        [t("fr", "menu_topup")],
        [t("fr", "menu_account"), t("fr", "menu_affiliate")],
    ]
    assert "compte" in t("fr", "menu_account").lower()


def test_payment_keyboard_prioritizes_verification():
    keyboard = kb.paid_keyboard("fr", order_id=17)

    assert keyboard.inline_keyboard[0][0].callback_data == "copy_binance_id:17"
    assert keyboard.inline_keyboard[0][1].callback_data == "copy_amount:17"
    assert keyboard.inline_keyboard[1][0].callback_data == "paid:17"


def test_support_flow_always_offers_a_home_action():
    keyboard = kb.support_category_keyboard("fr")

    assert keyboard.inline_keyboard[-1][0].callback_data == "home"


def test_payment_scanner_moves_without_fake_percentage():
    first = payment_scanner_frame(0)
    second = payment_scanner_frame(1)

    assert first != second
    assert first.count("💠") == 1
    assert "%" not in first + second


def test_inline_home_exposes_every_primary_journey():
    keyboard = kb.home_keyboard("fr", user_id=42)
    callbacks = {button.callback_data for row in keyboard.inline_keyboard for button in row}

    assert {"catalog", "orders", "topup", "account", "affiliate", "support", "language"} <= callbacks
    assert "help" not in callbacks


def test_onboarding_has_three_steps_and_catalog_cta():
    assert kb.onboarding_keyboard("fr", 1).inline_keyboard[0][0].callback_data == "tour:2"
    assert kb.onboarding_keyboard("fr", 2).inline_keyboard[0][0].callback_data == "tour:3"
    assert kb.onboarding_keyboard("fr", 3).inline_keyboard[0][0].callback_data == "catalog"


def test_welcome_banner_is_packaged_with_the_bot():
    banner = Path(__file__).resolve().parents[1] / "assets" / "blackmarket-welcome-v2.png"

    assert banner.exists()
    assert banner.stat().st_size > 100_000


def test_catalog_button_opens_the_services_catalog(monkeypatch):
    query = SimpleNamespace(
        data="catalog",
        from_user=SimpleNamespace(id=42),
        message=SimpleNamespace(text="Home"),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr("bot.lang_of", lambda _user_id: "fr")

    asyncio.run(cb_navigation(update, SimpleNamespace()))

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    call = query.edit_message_text.await_args
    assert "CATALOGUE" in call.args[0]
    callbacks = {
        button.callback_data
        for row in call.kwargs["reply_markup"].inline_keyboard
        for button in row
    }
    assert {"catalog", "home"} <= callbacks


def test_catalog_from_photo_caption_sends_a_new_text_screen(monkeypatch):
    message = SimpleNamespace(text=None, reply_text=AsyncMock())
    query = SimpleNamespace(
        data="catalog",
        from_user=SimpleNamespace(id=42),
        message=message,
        answer=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr("bot.lang_of", lambda _user_id: "en")

    asyncio.run(cb_navigation(update, SimpleNamespace()))

    message.reply_text.assert_awaited_once()
    assert "CATALOG" in message.reply_text.await_args.args[0]
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)


def test_orders_are_grouped_by_service_with_counts(monkeypatch):
    monkeypatch.setattr("bot.db.list_services", lambda: [
        {"name": "ChatGPT", "emoji": "🤖"},
        {"name": "Gemini", "emoji": "💡"},
    ])
    groups = order_service_groups([
        {"id": 1, "service_name": "Gemini"},
        {"id": 2, "service_name": "ChatGPT"},
        {"id": 3, "service_name": "ChatGPT"},
    ])

    assert [(group["name"], group["count"]) for group in groups] == [
        ("ChatGPT", 2),
        ("Gemini", 1),
    ]
    assert groups[0]["emoji"] == "🤖"


def test_orders_export_contains_summary_without_delivery_secret():
    content = orders_text_export("en", [{
        "id": 7,
        "service_name": "ChatGPT",
        "offer_name": "Plus",
        "qty": 2,
        "total_price": 18.0,
        "currency": "USDT",
        "status": "delivered",
        "created_at": 1_700_000_000,
        "delivery_text": "SECRET-CREDENTIAL",
    }], "ChatGPT")

    assert "Order #7" in content
    assert "ChatGPT" in content
    assert "18.00 USDT" in content
    assert "SECRET-CREDENTIAL" not in content
