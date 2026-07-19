"""Regression tests for the customer-facing Telegram navigation."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram.constants import ParseMode

import keyboards as kb
import database as db
from app.domain import affiliate_service
from bot import (
    AUTO_PAYMENT_MESSAGES,
    AUTO_PAYMENT_TASKS,
    cb_admin,
    cb_navigation,
    compact_offer_text,
    custom_emoji_from_message,
    custom_emojis_from_message,
    text_without_custom_emojis,
    text_with_custom_emoji_tokens,
    order_service_groups,
    orders_text_export,
    numbered_delivery_content,
    notify_successful_referral,
    payment_scanner_frame,
    premium_customer_text,
    rich_text_from_message,
    send_main_menu,
    stop_auto_payment_check,
)
from i18n import t


def test_delivery_accounts_are_numbered_in_order():
    assert numbered_delivery_content(["first@example.com:pass", "second@example.com:pass"]) == (
        "#1\nfirst@example.com:pass\n\n#2\nsecond@example.com:pass"
    )

def test_main_menu_is_compact_and_actions_match_labels():
    keyboard = kb.main_menu_keyboard("fr", user_id=42)

    labels = [[button.text for button in row] for row in keyboard.keyboard[:3]]
    assert labels == [
        [t("fr", "menu_catalog"), t("fr", "menu_orders")],
        [t("fr", "menu_topup")],
        [t("fr", "menu_account"), t("fr", "menu_affiliate")],
    ]
    assert "compte" in t("fr", "menu_account").lower()


def test_admin_custom_emoji_is_extracted_from_telegram_entity():
    message = SimpleNamespace(entities=[SimpleNamespace(
        type="custom_emoji",
        custom_emoji_id="animated-emoji-123",
    )])

    assert custom_emoji_from_message(message) == "animated-emoji-123"


def test_admin_text_category_button_opens_category(monkeypatch):
    query = SimpleNamespace(
        data="adm_text_cat:payments:0",
        from_user=SimpleNamespace(id=999),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    monkeypatch.setattr("bot.ADMIN_ID", 999)

    asyncio.run(cb_admin(SimpleNamespace(callback_query=query), SimpleNamespace()))

    query.edit_message_text.assert_awaited_once()
    keyboard = query.edit_message_text.await_args.kwargs["reply_markup"]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "adm_text_key:order_created" in callbacks or any(
        value and value.startswith("adm_text_cat:payments:") for value in callbacks
    )


def test_all_premium_emojis_are_detected_with_text_and_duplicates_removed():
    message = SimpleNamespace(
        entities=[
            SimpleNamespace(type="custom_emoji", custom_emoji_id="premium-1"),
            SimpleNamespace(type="bold", custom_emoji_id=None),
            SimpleNamespace(type="custom_emoji", custom_emoji_id="premium-2"),
            SimpleNamespace(type="custom_emoji", custom_emoji_id="premium-1"),
        ],
        caption_entities=[],
        text="Premium offer with animated emojis",
    )
    assert custom_emojis_from_message(message) == ["premium-1", "premium-2"]
    assert custom_emoji_from_message(message) == "premium-1"


def test_premium_emoji_placeholder_is_removed_from_button_text():
    message = SimpleNamespace(
        text="🔄 Refresh",
        caption=None,
        entities=[SimpleNamespace(type="custom_emoji", custom_emoji_id="premium-refresh", offset=0, length=2)],
        caption_entities=[],
    )
    assert text_without_custom_emojis(message) == "Refresh"


def test_multiple_premium_emojis_keep_exact_ids_and_positions():
    message = SimpleNamespace(
        text="A⭐ B🔥",
        caption=None,
        entities=[
            SimpleNamespace(type="custom_emoji", custom_emoji_id="premium-star", offset=1, length=1),
            SimpleNamespace(type="custom_emoji", custom_emoji_id="premium-fire", offset=4, length=2),
        ],
        caption_entities=[],
    )
    stored = text_with_custom_emoji_tokens(message)
    db.set_text_override("order_created", "en", stored, "premium-star")

    rendered = premium_customer_text("en", "order_created")

    assert rendered.startswith('A<tg-emoji emoji-id="premium-star">⭐</tg-emoji> B')
    assert '<tg-emoji emoji-id="premium-fire">🔥</tg-emoji>' in rendered
    assert rendered.count("<tg-emoji") == 2


def test_offer_description_preserves_telegram_rich_formatting(monkeypatch):
    message = SimpleNamespace(
        text="Premium description",
        text_html=(
            '<tg-emoji emoji-id="premium-description">💬</tg-emoji> '
            '<b>Premium</b> <i>description</i>'
        ),
        caption_html=None,
    )
    stored = rich_text_from_message(message)
    monkeypatch.setattr("bot.db.offer_sold_count", lambda _offer_id: 0)

    rendered = compact_offer_text({
        "id": 1, "name": "Plan", "price": 5.0, "stock": 2,
        "description": stored, "instructions": "—", "note": "Warranty",
    }, "en")

    assert '<tg-emoji emoji-id="premium-description">💬</tg-emoji>' in rendered
    assert "<b>Premium</b> <i>description</i>" in rendered


def test_plain_offer_description_does_not_treat_stars_or_underscores_as_markup(monkeypatch):
    monkeypatch.setattr("bot.db.offer_sold_count", lambda _offer_id: 0)

    rendered = compact_offer_text({
        "id": 1, "name": "Plan", "price": 5.0, "stock": 2,
        "description": "* ChatGPT: Icloud_mail\n* Mailbox: Icloud_mail",
        "instructions": "—", "note": "Warranty",
    }, "en")

    assert "* ChatGPT: Icloud_mail" in rendered
    assert "<i>" not in rendered
    assert "INSTRUCTIONS" not in rendered
    assert "Tap Buy now" not in rendered


def test_payment_keyboard_prioritizes_verification():
    keyboard = kb.paid_keyboard("fr", order_id=17, binance_id="454813844", total="5.00")

    assert keyboard.inline_keyboard[0][0].callback_data == "verify_auto:17"
    assert all(
        button.copy_text is None
        for row in keyboard.inline_keyboard
        for button in row
    )
    assert kb.txid_verify_keyboard("fr", 17).inline_keyboard[0][0].callback_data == "paid:17"
    assert kb.txid_verify_keyboard("fr", 17).inline_keyboard[1][0].callback_data == "cancel_buy:17"


def test_txid_verification_stops_scanner_and_deletes_waiting_message():
    async def scenario():
        scanner = SimpleNamespace(delete=AsyncMock())
        task = asyncio.create_task(asyncio.sleep(60))
        AUTO_PAYMENT_TASKS[17] = task
        AUTO_PAYMENT_MESSAGES[17] = scanner

        await stop_auto_payment_check(17)

        assert task.cancelled()
        scanner.delete.assert_awaited_once()
        assert 17 not in AUTO_PAYMENT_TASKS
        assert 17 not in AUTO_PAYMENT_MESSAGES

    asyncio.run(scenario())


def test_support_flow_always_offers_a_home_action():
    keyboard = kb.support_category_keyboard("fr")

    assert keyboard.inline_keyboard[-1][0].callback_data == "home"


def test_referrer_receives_progress_and_wallet_success_messages(mock_mongodb):
    referrer_id = 999
    mock_mongodb.users.insert_one({"telegram_id": referrer_id, "lang": "en"})
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    for index in range(9):
        user_id = 100 + index
        mock_mongodb.users.insert_one({"telegram_id": user_id})
        assert affiliate_service.register_referral_link(user_id, referrer_id)
    asyncio.run(notify_successful_referral(context, referrer_id))
    progress_message = context.bot.send_message.await_args.args[1]
    assert "9/10" in progress_message
    assert "2 USDT" in progress_message

    mock_mongodb.users.insert_one({"telegram_id": 109})
    assert affiliate_service.register_referral_link(109, referrer_id)
    asyncio.run(notify_successful_referral(context, referrer_id))
    success_message = context.bot.send_message.await_args.args[1]
    assert "10 valid referrals" in success_message
    assert "2 USDT" in success_message
    assert "2.00 USDT" in success_message


def test_payment_scanner_moves_without_fake_percentage():
    first = payment_scanner_frame(0)
    second = payment_scanner_frame(1)

    assert first != second
    assert first.count("💠") == 1
    assert "%" not in first + second


def test_payment_text_uses_exact_admin_premium_emoji_and_html():
    db.set_text_override(
        "payment_scanner",
        "en",
        "*BINANCE PAY DETECTION*\n`{frame}`\nOrder #{oid}",
        "premium-scanner-emoji-id",
    )

    rendered = premium_customer_text("en", "payment_scanner", frame="SCAN", oid=18)

    assert rendered.startswith(
        '<tg-emoji emoji-id="premium-scanner-emoji-id">⭐</tg-emoji> '
    )
    assert "<b>BINANCE PAY DETECTION</b>" in rendered
    assert "<code>SCAN</code>" in rendered
    assert "Order #18" in rendered


def test_order_payment_values_are_individually_copyable():
    db.set_text_override(
        "order_created",
        "en",
        "SEND EXACTLY: {total} {cur}\nBinance ID: {binance_id}\nMemo: {telegram_id}",
    )

    rendered = premium_customer_text(
        "en", "order_created", total="10.00", cur="USDT",
        binance_id="454813844", telegram_id="5141968904",
    )

    assert "<code>10.00</code> USDT" in rendered
    assert "Binance ID: <code>454813844</code>" in rendered
    assert "Memo: <code>5141968904</code>" in rendered


@pytest.mark.parametrize("key", [
    "order_created", "payment_scanner", "payment_scanner_success",
    "payment_scanner_timeout", "auto_check_timeout", "verifying", "verify_ok",
    "already_paid", "txid_too_short", "payment_wrong_amount",
    "payment_wrong_currency", "payment_wrong_memo", "payment_not_found",
    "payment_txid_used", "verify_failed", "delivery_received",
    "loyalty_activated", "affiliate_rewarded",
])
def test_all_payment_flow_texts_support_exact_premium_emoji(key):
    emoji_id = f"premium-{key}"
    db.set_text_override(key, "en", "Configurable payment text", emoji_id)

    rendered = premium_customer_text("en", key)

    assert f'<tg-emoji emoji-id="{emoji_id}">' in rendered


def test_dynamic_orders_button_supports_admin_premium_emoji():
    db.set_text_override("orders_all", "en", "All orders ({count})", "premium-orders-all")

    keyboard = kb.orders_services_keyboard("en", [], 8)

    assert keyboard.inline_keyboard[0][0].icon_custom_emoji_id == "premium-orders-all"


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


def test_main_menu_sends_welcome_banner_by_cached_url(monkeypatch):
    message = SimpleNamespace(reply_photo=AsyncMock(), reply_text=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        message=message,
        callback_query=None,
    )
    monkeypatch.setenv("HP_PUBLIC_BASE_URL", "https://shop.example")
    monkeypatch.setattr("bot.db.shop_settings", lambda: {"welcome_message": ""})

    asyncio.run(send_main_menu(update, SimpleNamespace(), "en"))

    message.reply_photo.assert_awaited_once()
    assert message.reply_photo.await_args.kwargs["photo"] == (
        "https://shop.example/assets/blackmarket-welcome-v2.png"
    )
    message.reply_text.assert_not_awaited()


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


def test_offer_back_button_from_photo_opens_service_without_editing_photo(monkeypatch):
    message = SimpleNamespace(text=None, reply_text=AsyncMock())
    query = SimpleNamespace(
        data="svc:7",
        from_user=SimpleNamespace(id=42),
        message=message,
        answer=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
    )
    monkeypatch.setattr("bot.lang_of", lambda _user_id: "en")
    monkeypatch.setattr("bot.db.get_service", lambda _sid: {"id": 7, "name": "Chat GPT", "emoji": "🤖"})
    monkeypatch.setattr("bot.db.list_offers", lambda _sid: [{"id": 9, "name": "30 days", "stock": 5}])
    monkeypatch.setattr("bot.kb.offers_keyboard", lambda _lang, _sid: Mock())

    asyncio.run(cb_navigation(SimpleNamespace(callback_query=query), SimpleNamespace()))

    message.reply_text.assert_awaited_once()
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)


def test_support_button_from_photo_sends_valid_html_contact(monkeypatch):
    message = SimpleNamespace(text=None, reply_text=AsyncMock())
    query = SimpleNamespace(
        data="support",
        from_user=SimpleNamespace(id=42),
        message=message,
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=query.from_user,
        effective_message=message,
    )
    monkeypatch.setattr("bot.lang_of", lambda _user_id: "en")

    asyncio.run(cb_navigation(update, SimpleNamespace()))

    message.reply_text.assert_awaited_once()
    call = message.reply_text.await_args
    assert "@Anwer_07" in call.args[0]
    assert call.kwargs["parse_mode"] == ParseMode.HTML


def test_admin_from_photo_caption_sends_a_new_text_panel(monkeypatch):
    message = SimpleNamespace(text=None, reply_text=AsyncMock())
    query = SimpleNamespace(
        data="adm_panel",
        from_user=SimpleNamespace(id=999),
        message=message,
        answer=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr("bot.ADMIN_ID", 999)

    asyncio.run(cb_admin(update, SimpleNamespace()))

    message.reply_text.assert_awaited_once()
    assert "Panneau Admin" in message.reply_text.await_args.args[0]
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)


def test_cancel_payment_button_cancels_the_customers_order(monkeypatch):
    query = SimpleNamespace(
        data="cancel_buy:17",
        from_user=SimpleNamespace(id=42),
        message=SimpleNamespace(text="Payment"),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    cancelled = []
    monkeypatch.setattr("bot.lang_of", lambda _user_id: "en")
    monkeypatch.setattr("bot.db.get_order", lambda order_id: {"id": order_id, "user_id": 42})
    monkeypatch.setattr(
        "bot.order_service.cancel_order",
        lambda order_id, reason="": cancelled.append((order_id, reason)) or True,
    )

    asyncio.run(cb_navigation(update, SimpleNamespace()))

    assert cancelled == [(17, "Cancelled by customer")]
    query.edit_message_text.assert_awaited_once()


def test_cancel_payment_button_cannot_cancel_another_users_order(monkeypatch):
    query = SimpleNamespace(
        data="cancel_buy:17",
        from_user=SimpleNamespace(id=42),
        message=SimpleNamespace(text="Payment"),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    cancel_order = Mock()
    monkeypatch.setattr("bot.lang_of", lambda _user_id: "en")
    monkeypatch.setattr("bot.db.get_order", lambda _order_id: {"id": 17, "user_id": 99})
    monkeypatch.setattr("bot.order_service.cancel_order", cancel_order)

    asyncio.run(cb_navigation(update, SimpleNamespace()))

    cancel_order.assert_not_called()


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
