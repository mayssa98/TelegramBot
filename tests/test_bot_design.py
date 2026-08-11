"""Regression tests for the customer-facing Telegram navigation."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram.constants import ParseMode

import database as db
import keyboards as kb
from app.domain import affiliate_service, support_service
from bot import (
    PENDING,
    announce_channel_purchase,
    announce_channel_restock,
    announce_flash_sale,
    block_maintenance_users,
    broadcast_admin_message,
    broadcast_maintenance_notice,
    cb_admin,
    cb_navigation,
    cmd_start,
    compact_offer_text,
    custom_emoji_from_message,
    custom_emojis_from_message,
    handle_buy_confirmed,
    handle_pending_input,
    handle_ticket_attachment,
    notify_admin_interaction,
    notify_successful_referral,
    numbered_delivery_content,
    on_text_menu,
    order_service_groups,
    orders_text_export,
    premium_customer_text,
    rich_text_from_message,
    send_main_menu,
    send_payment_result,
    text_with_custom_emoji_tokens,
    text_without_custom_emojis,
)
from i18n import t


def test_inventory_restock_is_broadcast_privately_to_all_bot_users(mock_mongodb):
    service_id = db.add_service("Chat GPT", "🤖")
    offer_id = db.add_offer(service_id, "Premium 30 days", 5.0, 3)
    mock_mongodb.users.insert_many([
        {"telegram_id": 101, "lang": "en"},
        {"telegram_id": 202, "lang": "en"},
    ])
    bot_client = SimpleNamespace(username="blackmarketa_bot", send_message=AsyncMock())

    sent = asyncio.run(announce_channel_restock(SimpleNamespace(bot=bot_client), offer_id, 3, 3))

    assert sent == 2
    assert bot_client.send_message.await_count == 2
    calls = bot_client.send_message.await_args_list
    assert {call.kwargs["chat_id"] for call in calls} == {101, 202}
    assert all(call.kwargs["chat_id"] != "@blackmarketBotChannel" for call in calls)
    assert all("NEW STOCK JUST DROPPED" in call.kwargs["text"] for call in calls)
    assert all(
        call.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == f"buy:{offer_id}"
        for call in calls
    )


def test_flash_sale_is_broadcast_with_buy_button(mock_mongodb):
    service_id = db.add_service("AI", "⚡")
    offer_id = db.add_offer(service_id, "Gemini Pro 18M", 8.0, 4)
    db.start_flash_sale(offer_id, 3.0, 480)
    mock_mongodb.users.insert_one({"telegram_id": 101, "lang": "en"})
    bot_client = SimpleNamespace(send_message=AsyncMock())

    sent = asyncio.run(announce_flash_sale(SimpleNamespace(bot=bot_client), offer_id))

    assert sent == 1
    call = bot_client.send_message.await_args
    assert "FLASH SALE" in call.kwargs["text"]
    assert "8.00 USDT" in call.kwargs["text"]
    assert "3.00 USDT" in call.kwargs["text"]
    assert call.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == f"buy:{offer_id}"


def test_admin_can_reannounce_current_offer_without_adding_stock(mock_mongodb):
    service_id = db.add_service("Chat GPT", "🤖")
    offer_id = db.add_offer(service_id, "Premium 30 days", 7.5, 4)
    mock_mongodb.users.insert_one({"telegram_id": 101, "lang": "en"})
    bot_client = SimpleNamespace(send_message=AsyncMock())

    sent = asyncio.run(
        announce_channel_restock(SimpleNamespace(bot=bot_client), offer_id, None, 4)
    )

    assert sent == 1
    text = bot_client.send_message.await_args.kwargs["text"]
    assert "AVAILABLE OFFER" in text
    assert "7.50 USDT" in text
    assert "4 account" in text


def test_admin_custom_announcement_is_copied_to_all_active_users(mock_mongodb):
    mock_mongodb.users.insert_many([
        {"telegram_id": 101, "lang": "en"},
        {"telegram_id": 202, "lang": "en"},
        {"telegram_id": 303, "lang": "en", "banned": True},
    ])
    bot_client = SimpleNamespace(copy_message=AsyncMock())

    sent = asyncio.run(
        broadcast_admin_message(
            SimpleNamespace(bot=bot_client),
            source_chat_id=999,
            message_id=55,
        )
    )

    assert sent == 2
    assert bot_client.copy_message.await_count == 2
    assert {
        call.kwargs["chat_id"]
        for call in bot_client.copy_message.await_args_list
    } == {101, 202}
    assert all(
        call.kwargs["from_chat_id"] == 999 and call.kwargs["message_id"] == 55
        for call in bot_client.copy_message.await_args_list
    )


def test_maintenance_notice_is_sent_to_every_active_user(mock_mongodb):
    mock_mongodb.users.insert_many([
        {"telegram_id": 101, "lang": "en"},
        {"telegram_id": 202, "lang": "en"},
        {"telegram_id": 303, "lang": "en", "banned": True},
    ])
    bot_client = SimpleNamespace(send_message=AsyncMock())

    sent = asyncio.run(
        broadcast_maintenance_notice(
            SimpleNamespace(bot=bot_client),
            "The shop is temporarily unavailable.",
        )
    )

    assert sent == 2
    assert {
        call.kwargs["chat_id"]
        for call in bot_client.send_message.await_args_list
    } == {101, 202}
    assert all(
        "The shop is temporarily unavailable." in call.kwargs["text"]
        for call in bot_client.send_message.await_args_list
    )


def test_full_maintenance_blocks_every_customer_command(monkeypatch):
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    monkeypatch.setattr("bot.db.shop_settings", lambda: {
        "maintenance_enabled": True,
        "maintenance_message": "We will be back shortly.",
    })
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        callback_query=None,
        effective_message=message,
    )

    with pytest.raises(Exception) as stopped:
        asyncio.run(block_maintenance_users(update, SimpleNamespace()))

    assert stopped.value.__class__.__name__ == "ApplicationHandlerStop"
    message.reply_text.assert_awaited_once()
    assert "BOT UNDER MAINTENANCE" in message.reply_text.await_args.args[0]
    assert "We will be back shortly." in message.reply_text.await_args.args[0]


def test_full_maintenance_blocks_customer_buttons(monkeypatch):
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    monkeypatch.setattr("bot.db.shop_settings", lambda: {
        "maintenance_enabled": True,
        "maintenance_message": "Please try later.",
    })
    message = SimpleNamespace(reply_text=AsyncMock())
    query = SimpleNamespace(answer=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        callback_query=query,
        effective_message=message,
    )

    with pytest.raises(Exception):
        asyncio.run(block_maintenance_users(update, SimpleNamespace()))

    query.answer.assert_awaited_once_with("Maintenance mode is active.", show_alert=True)
    message.reply_text.assert_awaited_once()


def test_full_maintenance_never_blocks_admin(monkeypatch):
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    monkeypatch.setattr("bot.db.shop_settings", Mock(side_effect=AssertionError("not needed")))
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=999),
        callback_query=None,
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )

    asyncio.run(block_maintenance_users(update, SimpleNamespace()))

    update.effective_message.reply_text.assert_not_awaited()


def test_customer_button_click_is_reported_to_private_channel(monkeypatch, mock_mongodb):
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    monkeypatch.setattr("bot.CLICK_REPORT_CHAT_ID", -1004349965359)
    bot_client = SimpleNamespace(send_message=AsyncMock())
    message = SimpleNamespace(
        text="Offer screen",
        caption=None,
        reply_markup=SimpleNamespace(inline_keyboard=[[
            SimpleNamespace(text="Buy Premium now", callback_data="buy:17"),
        ]]),
    )
    query = SimpleNamespace(data="buy:17", message=message)
    user = SimpleNamespace(
        id=42, full_name="Test Buyer", first_name="Test",
        username="buyer",
    )
    update = SimpleNamespace(
        effective_user=user,
        callback_query=query,
        effective_message=message,
    )

    asyncio.run(
        notify_admin_interaction(update, SimpleNamespace(bot=bot_client))
    )

    bot_client.send_message.assert_awaited_once()
    call = bot_client.send_message.await_args
    assert call.args[0] == -1004349965359
    assert "buy:17" in call.args[1]
    assert "Buy Premium now" in call.args[1]
    assert "CUSTOMER CLICK" in call.args[1]
    assert "Test Buyer" in call.args[1]
    assert "42" in call.args[1]
    event = mock_mongodb.interaction_events.find_one({"user_id": 42})
    assert event["interaction_type"] == "button"
    assert event["action"] == "buy:17"


def test_customer_message_is_not_sent_to_click_channel(mock_mongodb):
    bot_client = SimpleNamespace(send_message=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        callback_query=None,
        effective_message=SimpleNamespace(text="support message"),
    )

    asyncio.run(
        notify_admin_interaction(update, SimpleNamespace(bot=bot_client))
    )

    bot_client.send_message.assert_not_awaited()
    assert mock_mongodb.interaction_events.count_documents({}) == 0


def test_admin_interaction_does_not_notify_itself(monkeypatch):
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    bot_client = SimpleNamespace(send_message=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=999),
        callback_query=None,
        effective_message=SimpleNamespace(text="/admin"),
    )

    asyncio.run(
        notify_admin_interaction(update, SimpleNamespace(bot=bot_client))
    )

    bot_client.send_message.assert_not_awaited()


def test_successful_purchase_is_not_announced_to_channel(mock_mongodb):
    service_id = db.add_service("Chat GPT", "🤖")
    offer_id = db.add_offer(service_id, "Premium 30 days", 5.0, 4)
    mock_mongodb.orders.insert_one({
        "id": 77,
        "user_id": 987654321,
        "offer_id": offer_id,
        "service_name": "Chat GPT",
        "offer_name": "Premium 30 days",
        "qty": 2,
        "unit_price": 5.0,
        "gross_total": 10.0,
        "currency": "USDT",
        "status": "delivered",
        "txid": "REAL_TXID_SECRET",
        "verify_method": "binance",
    })
    bot_client = SimpleNamespace(username="blackmarketa_bot", send_message=AsyncMock())
    context = SimpleNamespace(bot=bot_client)

    first = asyncio.run(announce_channel_purchase(context, 77))
    second = asyncio.run(announce_channel_purchase(context, 77))

    assert first is False
    assert second is False
    bot_client.send_message.assert_not_awaited()


def test_admin_test_purchase_is_never_announced(mock_mongodb):
    mock_mongodb.orders.insert_one({
        "id": 78, "offer_id": 1, "status": "delivered", "verify_method": "admin_test",
    })
    bot_client = SimpleNamespace(username="blackmarketa_bot", send_message=AsyncMock())

    sent = asyncio.run(announce_channel_purchase(SimpleNamespace(bot=bot_client), 78))

    assert sent == 0
    bot_client.send_message.assert_not_awaited()

def test_zero_added_inventory_does_not_announce(mock_mongodb):
    bot_client = SimpleNamespace(username="blackmarketa_bot", send_message=AsyncMock())

    sent = asyncio.run(announce_channel_restock(SimpleNamespace(bot=bot_client), 99, 0, 4))

    assert sent == 0
    bot_client.send_message.assert_not_awaited()

def test_delivery_accounts_use_numeric_labels_without_hash_delimiters():
    assert numbered_delivery_content([
        "first@example.com:pass",
        "#second@example.com:pass",
        "#3\nthird@example.com:pass",
    ]) == (
        "1.\nfirst@example.com:pass\n\n2.\nsecond@example.com:pass\n\n3.\nthird@example.com:pass"
    )

def test_start_allows_access_without_channel_or_group_membership(monkeypatch):
    message = SimpleNamespace(reply_text=AsyncMock())
    user = SimpleNamespace(id=42, username="buyer", first_name="Buyer")
    bot_client = SimpleNamespace(
        username="blackmarketa_bot",
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="left")),
    )
    update = SimpleNamespace(effective_user=user, message=message)
    context = SimpleNamespace(bot=bot_client, args=[])
    monkeypatch.setattr("bot.ADMIN_ID", 999)

    asyncio.run(cmd_start(update, context))

    message.reply_text.assert_awaited_once()
    call = message.reply_text.await_args
    assert "WELCOME TO" in call.args[0]
    assert call.kwargs["reply_markup"] is not None
    bot_client.get_chat_member.assert_not_awaited()


def test_verify_joining_unlocks_marketing_welcome(monkeypatch):
    message = SimpleNamespace(reply_text=AsyncMock())
    query = SimpleNamespace(
        data="verify_channel_join",
        from_user=SimpleNamespace(id=42),
        message=message,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    bot_client = SimpleNamespace(
        username="blackmarket_test_bot",
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")),
    )
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    db.upsert_user(42, "buyer", "Buyer")
    PENDING[42] = ("await_channel_join", 0)

    asyncio.run(cb_navigation(SimpleNamespace(callback_query=query), SimpleNamespace(bot=bot_client)))

    query.edit_message_text.assert_awaited_once()
    rendered = query.edit_message_text.await_args.args[0]
    assert "WELCOME TO" in rendered
    assert "1 USDT" in rendered
    assert "12% OFF" in rendered
    assert query.edit_message_text.await_args.kwargs["parse_mode"] == ParseMode.HTML
    bot_client.get_chat_member.assert_not_awaited()


def test_group_membership_is_also_required(monkeypatch):
    from bot import is_required_channel_member

    bot_client = SimpleNamespace(get_chat_member=AsyncMock(side_effect=[
        SimpleNamespace(status="member"),
        SimpleNamespace(status="left"),
    ]))
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    monkeypatch.setattr("bot.REQUIRED_CHANNEL", "@channel")
    monkeypatch.setattr("bot.REQUIRED_GROUP", "@Blackmarketgrp")

    assert asyncio.run(is_required_channel_member(bot_client, 42)) is False
    assert [call.args[0] for call in bot_client.get_chat_member.await_args_list] == [
        "@channel", "@Blackmarketgrp",
    ]


def test_membership_check_accepts_links_and_numeric_chat_ids(monkeypatch):
    from bot import is_required_channel_member

    bot_client = SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")))
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    monkeypatch.setattr("bot.REQUIRED_CHANNEL", "https://t.me/blackmarketBotChannel")
    monkeypatch.setattr("bot.REQUIRED_GROUP", "-1001234567890")

    assert asyncio.run(is_required_channel_member(bot_client, 42)) is True
    assert [call.args[0] for call in bot_client.get_chat_member.await_args_list] == [
        "@blackmarketBotChannel", -1001234567890,
    ]


def test_membership_check_resolves_usernames_to_numeric_chat_ids(monkeypatch):
    from bot import required_membership_status

    bot_client = SimpleNamespace(
        get_chat=AsyncMock(side_effect=[
            SimpleNamespace(id=-100111, title="Black Market Channel"),
            SimpleNamespace(id=-100222, title="Black Market Group"),
        ]),
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")),
    )
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    monkeypatch.setattr("bot.REQUIRED_CHANNEL", "@blackmarketBotChannel")
    monkeypatch.setattr("bot.REQUIRED_GROUP", "@Blackmarketgrp")

    allowed, details = asyncio.run(required_membership_status(bot_client, 42))

    assert allowed is True
    assert [call.args[0] for call in bot_client.get_chat_member.await_args_list] == [
        -100111, -100222,
    ]
    assert [detail["title"] for detail in details] == [
        "Black Market Channel", "Black Market Group",
    ]


def test_membership_check_accepts_owner_status(monkeypatch):
    from bot import is_required_channel_member

    bot_client = SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status="owner")))
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    monkeypatch.setattr("bot.REQUIRED_CHANNEL", "@channel")
    monkeypatch.setattr("bot.REQUIRED_GROUP", "@group")

    assert asyncio.run(is_required_channel_member(bot_client, 42)) is True


def test_membership_status_reports_failed_chat(monkeypatch):
    from bot import required_membership_status

    bot_client = SimpleNamespace(get_chat_member=AsyncMock(side_effect=[
        SimpleNamespace(status="member"),
        SimpleNamespace(status="left"),
    ]))
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    monkeypatch.setattr("bot.REQUIRED_CHANNEL", "@channel")
    monkeypatch.setattr("bot.REQUIRED_GROUP", "@group")

    allowed, details = asyncio.run(required_membership_status(bot_client, 42))

    assert allowed is False
    assert details == [
        {"chat": "@channel", "ok": True, "status": "member"},
        {"chat": "@group", "ok": False, "status": "left"},
    ]


def test_legacy_verify_button_unlocks_without_membership(monkeypatch):
    message = SimpleNamespace(reply_text=AsyncMock())
    query = SimpleNamespace(
        data="verify_channel_join",
        from_user=SimpleNamespace(id=42),
        message=message,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    bot_client = SimpleNamespace(
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="left")),
        send_message=AsyncMock(),
        username="blackmarket_test_bot",
    )
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    monkeypatch.setattr("bot.REQUIRED_CHANNEL", "@channel")
    monkeypatch.setattr("bot.REQUIRED_GROUP", "@group")

    asyncio.run(cb_navigation(SimpleNamespace(callback_query=query), SimpleNamespace(bot=bot_client)))

    bot_client.get_chat_member.assert_not_awaited()
    bot_client.send_message.assert_not_awaited()
    query.edit_message_text.assert_awaited_once()
    assert "WELCOME TO" in query.edit_message_text.await_args.args[0]

@pytest.mark.parametrize(
    ("key", "incoming_text", "emoji_id"),
    [
        ("menu_topup", "💳 Top Up Balance", "premium-topup"),
        ("menu_account", "👤 My account", "premium-profile"),
    ],
)
def test_admin_can_edit_topup_and_profile_even_when_text_matches_current_button(
    mock_mongodb, monkeypatch, key, incoming_text, emoji_id,
):
    admin_id = 999
    db.upsert_user(admin_id, "admin", "Admin")
    db.set_user_lang(admin_id, "en")
    PENDING[admin_id] = ("adm_text_override", f"{key}|en")
    message = SimpleNamespace(
        text=incoming_text,
        caption=None,
        entities=[SimpleNamespace(type="custom_emoji", custom_emoji_id=emoji_id, offset=0, length=2)],
        caption_entities=[],
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=admin_id),
        message=message,
    )
    monkeypatch.setattr("bot.ADMIN_ID", admin_id)

    asyncio.run(on_text_menu(update, SimpleNamespace()))

    assert db.get_text_override(key, "en") in {"Top Up Balance", "My account"}
    assert db.get_text_override_icon(key, "en") == emoji_id
    assert PENDING.get(admin_id) is None
    assert "enregistr" in message.reply_text.await_args.args[0].lower()

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


def test_channel_message_accepts_exact_premium_emojis_and_rich_text(mock_mongodb):
    db.set_text_override(
        "channel_purchase_success",
        "en",
        '[[HTML]]<tg-emoji emoji-id="premium-sale">🎉</tg-emoji> <b>New sale</b>',
        "premium-sale",
    )

    rendered = premium_customer_text("en", "channel_purchase_success")

    assert '<tg-emoji emoji-id="premium-sale">🎉</tg-emoji>' in rendered
    assert "<b>New sale</b>" in rendered

def test_premium_channel_html_also_renders_admin_markdown_markers(mock_mongodb):
    db.set_text_override(
        "channel_stock_announcement",
        "en",
        '[[HTML]]<tg-emoji emoji-id="premium-new">🆕</tg-emoji> *NEW STOCK* — _limited_',
        "premium-new",
    )

    rendered = premium_customer_text("en", "channel_stock_announcement")

    assert '<tg-emoji emoji-id="premium-new">🆕</tg-emoji>' in rendered
    assert "<b>NEW STOCK</b>" in rendered
    assert "<i>limited</i>" in rendered
    assert "*NEW STOCK*" not in rendered

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

    assert keyboard.inline_keyboard[0][0].callback_data == "paid:17"
    assert all(
        button.copy_text is None
        for row in keyboard.inline_keyboard
        for button in row
    )
    assert kb.txid_verify_keyboard("fr", 17).inline_keyboard[0][0].callback_data == "paid:17"
    assert kb.txid_verify_keyboard("fr", 17).inline_keyboard[1][0].callback_data == "cancel_buy:17"


@pytest.mark.parametrize("callback", ["paid:17", "verify_auto:17"])
def test_payment_buttons_route_to_txid_entry(callback, monkeypatch, mock_mongodb):
    message = SimpleNamespace(reply_text=AsyncMock())
    query = SimpleNamespace(
        data=callback,
        from_user=SimpleNamespace(id=42),
        message=message,
        answer=AsyncMock(),
    )
    monkeypatch.setattr("bot.lang_of", lambda _user_id: "en")

    asyncio.run(cb_navigation(
        SimpleNamespace(callback_query=query), SimpleNamespace(),
    ))

    assert PENDING.get(42) == ("await_txid", 17)
    assert "transaction ID" in message.reply_text.await_args.args[0]


def test_support_flow_always_offers_a_home_action():
    keyboard = kb.support_category_keyboard("fr")

    assert keyboard.inline_keyboard[-1][0].callback_data == "home"


def test_referrer_receives_progress_and_wallet_success_messages(mock_mongodb, monkeypatch):
    referrer_id = 999
    mock_mongodb.users.insert_one({"telegram_id": referrer_id, "lang": "en"})
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    monkeypatch.setattr("bot.REQUIRED_CHANNEL", "@affiliate_channel")

    for index in range(9):
        user_id = 100 + index
        mock_mongodb.users.insert_one({"telegram_id": user_id})
        assert affiliate_service.register_referral_link(user_id, referrer_id)
        mock_mongodb.orders.insert_one({"id": index + 1, "user_id": user_id, "total_price": 1.0})
        affiliate_service.on_confirmed_payment(user_id, index + 1)
    asyncio.run(notify_successful_referral(context, referrer_id))
    progress_message = context.bot.send_message.await_args.args[1]
    assert "9/10" in progress_message
    assert "2 USDT" in progress_message

    mock_mongodb.users.insert_one({"telegram_id": 109})
    assert affiliate_service.register_referral_link(109, referrer_id)
    mock_mongodb.orders.insert_one({"id": 10, "user_id": 109, "total_price": 1.0})
    affiliate_service.on_confirmed_payment(109, 10)
    asyncio.run(notify_successful_referral(context, referrer_id))
    private_call = context.bot.send_message.await_args_list[-1]
    success_message = private_call.args[1]
    assert private_call.args[0] == referrer_id
    assert "10 valid referrals" in success_message
    assert "2 USDT" in success_message
    assert "2.00 USDT" in success_message
    assert context.bot.send_message.await_count == 2


def test_order_payment_values_are_individually_copyable():
    db.set_text_override(
        "order_created",
        "en",
        "SEND EXACTLY: {total} {cur}\nBinance ID: {binance_id}",
    )

    rendered = premium_customer_text(
        "en", "order_created", total="10.00", cur="USDT",
        binance_id="454813844",
    )

    assert "<code>10.00</code> USDT" in rendered
    assert "Binance ID: <code>454813844</code>" in rendered
    assert "Memo" not in rendered


@pytest.mark.parametrize("key", [
    "order_created", "verifying", "verify_ok",
    "already_paid", "txid_too_short", "payment_wrong_amount",
    "payment_wrong_currency", "payment_not_found",
    "payment_txid_used", "verify_failed", "delivery_received",
    "loyalty_activated", "affiliate_rewarded",
    "topup_message", "topup_ask_txid",
    "topup_success", "topup_already_confirmed", "topup_failed",
    "flash_sale_announcement",
    "affiliate_referral_success", "affiliate_ten_success", "channel_affiliate_reward",
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


def test_out_of_stock_offer_click_sends_customer_message(monkeypatch):
    message = SimpleNamespace(reply_text=AsyncMock())
    query = SimpleNamespace(
        data="off:9",
        from_user=SimpleNamespace(id=42),
        message=message,
        answer=AsyncMock(),
    )
    monkeypatch.setattr("bot.lang_of", lambda _user_id: "en")
    monkeypatch.setattr("bot.db.get_offer", lambda _oid: {"id": 9, "stock": 0})

    asyncio.run(cb_navigation(SimpleNamespace(callback_query=query), SimpleNamespace()))

    message.reply_text.assert_awaited_once()
    assert "Out of stock" in message.reply_text.await_args.args[0]
    assert message.reply_text.await_args.kwargs["parse_mode"] == ParseMode.HTML

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


def test_support_button_from_photo_opens_ticket_categories(monkeypatch):
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
    assert "Choose the category" in call.args[0]
    callbacks = [
        button.callback_data for row in call.kwargs["reply_markup"].inline_keyboard
        for button in row
    ]
    assert "support_cat:other" in callbacks


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


def test_catalog_request_button_supports_admin_premium_emoji(mock_mongodb):
    db.set_text_override(
        "catalog_request_button", "en", "Request a product", "premium-catalog-request"
    )

    keyboard = kb.services_keyboard("en")
    button = next(
        button
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data == "catalog_request"
    )

    assert button.text == "Request a product"
    assert button.icon_custom_emoji_id == "premium-catalog-request"


def test_catalog_request_button_prompts_for_customer_need(monkeypatch, mock_mongodb):
    message = SimpleNamespace(reply_text=AsyncMock())
    query = SimpleNamespace(
        data="catalog_request",
        from_user=SimpleNamespace(id=42),
        message=message,
        answer=AsyncMock(),
    )
    monkeypatch.setattr("bot.lang_of", lambda _user_id: "en")

    asyncio.run(cb_navigation(SimpleNamespace(callback_query=query), SimpleNamespace()))

    assert PENDING.get(42) == ("catalog_request", 0)
    message.reply_text.assert_awaited_once()
    assert "Tell us what you need" in message.reply_text.await_args.args[0]
    PENDING.pop(42, None)


def test_catalog_request_is_saved_and_sent_to_support_channel(monkeypatch, mock_mongodb):
    create_ticket = Mock(return_value={
        "id": 17,
        "user_id": 42,
        "category": "catalog_request",
    })
    monkeypatch.setattr("bot.support_service.create_ticket", create_ticket)
    bot_client = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=801)),
    )
    message = SimpleNamespace(
        text="I need Microsoft 365 for one year",
        text_html=None,
        caption_html=None,
        entities=[],
        reply_text=AsyncMock(),
        delete=AsyncMock(),
    )
    user = SimpleNamespace(id=42, full_name="Test Customer", username="buyer")
    update = SimpleNamespace(effective_user=user, message=message)
    PENDING[42] = ("catalog_request", 0)

    asyncio.run(handle_pending_input(update, SimpleNamespace(bot=bot_client), "en"))

    create_ticket.assert_called_once_with(
        42, "I need Microsoft 365 for one year", category="catalog_request"
    )
    bot_client.send_message.assert_awaited_once()
    channel_call = bot_client.send_message.await_args
    assert channel_call.args[0] == -1004326329551
    assert "New catalog request" in channel_call.args[1]
    assert "Microsoft 365" in channel_call.args[1]
    assert PENDING.get(42) is None
    assert "Request sent" in message.reply_text.await_args.args[0]
    message.delete.assert_awaited_once()

def test_topup_keyboard_offers_bsc_and_polygon(mock_mongodb):
    callbacks = [
        button.callback_data
        for row in kb.topup_keyboard("en").inline_keyboard
        for button in row
    ]

    assert callbacks == ["topup_txid", "topup_bsc", "topup_polygon", "home"]


def test_topup_instructions_are_txid_only(mock_mongodb):
    message = t("en", "topup_message", binance_id="123")

    assert "Memo" not in message
    assert "Verify with TXID" in message

def test_every_topup_button_supports_exact_premium_emoji(mock_mongodb):
    overrides = {
        "topup_verify_txid": ("Verify with TXID", "premium-topup-txid"),
        "topup_home_button": ("Home", "premium-topup-home"),
    }
    for key, (label, emoji_id) in overrides.items():
        db.set_text_override(key, "en", label, emoji_id)

    initial = kb.topup_keyboard("en")
    buttons = {
        button.callback_data: button
        for keyboard in (initial,)
        for row in keyboard.inline_keyboard
        for button in row
    }

    assert buttons["topup_txid"].icon_custom_emoji_id == "premium-topup-txid"
    assert buttons["home"].icon_custom_emoji_id == "premium-topup-home"
    assert buttons["topup_txid"].text == "Verify with TXID"


def test_empty_wallet_click_always_returns_a_visible_message(monkeypatch):
    query = SimpleNamespace(
        data="pay_wallet:9:1",
        from_user=SimpleNamespace(id=42),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr("bot.db.get_offer", lambda _offer_id: {
        "id": 9, "price": 5.0, "stock": 1,
    })

    def reject_empty_wallet(*_args, **_kwargs):
        raise ValueError("Insufficient balance: 0.00 USDT available.")

    monkeypatch.setattr("bot.order_service.create_order", reject_empty_wallet)

    asyncio.run(handle_buy_confirmed(update, SimpleNamespace(), "en", "wallet"))

    query.message.reply_text.assert_awaited_once_with(
        "Insufficient balance: 0.00 USDT available."
    )


def test_otp_numbers_catalog_is_always_one_dollar_and_manual(mock_mongodb):
    service_id = db.add_service("OTP numbers", "OTP")
    offers = db.list_offers(service_id)
    assert len(offers) == 1
    offer_id = offers[0]["id"]

    raw = mock_mongodb.offers.find_one({"id": offer_id})
    offer = db.get_offer(offer_id)

    assert raw["price"] == 1.0
    assert raw["unlimited_stock"] is True
    assert raw["manual_stock"] is True
    assert raw["auto_delivery"] is False
    assert offer["price"] == 1.0
    assert db.offer_has_stock(offer, 50) is True

    db.update_offer(offer_id, price=25.0, auto_delivery=True, unlimited_stock=False)
    updated = mock_mongodb.offers.find_one({"id": offer_id})
    assert updated["price"] == 1.0
    assert updated["auto_delivery"] is False
    assert updated["unlimited_stock"] is True


def test_existing_otp_service_without_offers_self_heals(mock_mongodb):
    mock_mongodb.services.insert_one({
        "id": 77,
        "name": "OTP Numbers",
        "emoji": "OTP",
        "sort_order": 1,
        "active": 1,
    })

    first = db.list_offers(77)
    second = db.list_offers(77)

    assert len(first) == 1
    assert len(second) == 1
    assert first[0]["name"] == "OTP code"
    assert first[0]["price"] == 1.0
    assert first[0]["unlimited_stock"] is True
    assert first[0]["manual_stock"] is True
    assert mock_mongodb.offers.count_documents({"service_id": 77}) == 1


def test_automatically_delivered_paid_order_is_notified_to_admin(
    monkeypatch, mock_mongodb,
):
    mock_mongodb.orders.insert_one({
        "id": 500,
        "user_id": 42,
        "service_name": "Canva",
        "offer_name": "Canva Pro",
        "qty": 1,
        "status": "delivered",
    })
    notify_new_order = AsyncMock()
    monkeypatch.setattr("bot.admin.notify_new_order", notify_new_order)
    message = SimpleNamespace(reply_text=AsyncMock())

    asyncio.run(send_payment_result(
        message,
        SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock())),
        "en",
        500,
        {
            "status": "delivered",
            "affiliate": None,
            "loyalty": None,
            "delivered_content": ["account@example.com"],
        },
        42,
    ))

    notify_new_order.assert_awaited_once()
    assert notify_new_order.await_args.args[1]["id"] == 500


def test_manual_delivery_sends_admin_an_in_bot_reply_request(
    monkeypatch, mock_mongodb,
):
    mock_mongodb.orders.insert_one({
        "id": 503,
        "user_id": 42,
        "service_name": "Manual service",
        "offer_name": "Manual account",
        "qty": 1,
        "status": "paid",
    })
    notify_manual = AsyncMock()
    notify_new_order = AsyncMock()
    monkeypatch.setattr("bot.admin.notify_manual_delivery_request", notify_manual)
    monkeypatch.setattr("bot.admin.notify_new_order", notify_new_order)
    message = SimpleNamespace(reply_text=AsyncMock())

    asyncio.run(send_payment_result(
        message,
        SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock())),
        "en",
        503,
        {
            "status": "confirmed_no_delivery",
            "affiliate": None,
            "loyalty": None,
            "delivered_content": None,
        },
        42,
    ))

    notify_manual.assert_awaited_once()
    notify_new_order.assert_not_awaited()
    customer_keyboard = message.reply_text.await_args.kwargs["reply_markup"]
    assert customer_keyboard.inline_keyboard[0][0].callback_data == "catalog"


def test_paid_otp_order_asks_for_service_before_admin_handoff(mock_mongodb):
    mock_mongodb.orders.insert_one({
        "id": 501,
        "user_id": 42,
        "service_name": "OTP numbers",
        "offer_name": "OTP code",
        "qty": 2,
        "status": "payment_confirmed",
    })
    message = SimpleNamespace(reply_text=AsyncMock())

    asyncio.run(send_payment_result(
        message,
        SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock())),
        "en",
        501,
        {
            "status": "confirmed_no_delivery",
            "affiliate": None,
            "loyalty": None,
            "delivered_content": None,
        },
        42,
    ))

    assert PENDING.get(42) == ("otp_service", {"order_id": 501})
    assert "What's the service?" in message.reply_text.await_args.args[0]
    assert mock_mongodb.orders.find_one({"id": 501})["otp_workflow_status"] == "awaiting_service"


def test_otp_answers_notify_admin_and_redirect_customer(monkeypatch, mock_mongodb):
    monkeypatch.setattr("bot.ADMIN_ID", 999)
    mock_mongodb.orders.insert_one({
        "id": 502,
        "user_id": 42,
        "service_name": "OTP numbers",
        "offer_name": "OTP code",
        "qty": 3,
        "wallet_amount": 3.0,
        "total_price": 0.0,
        "payment_method": "wallet",
        "verify_method": "wallet",
        "txid": "",
        "status": "payment_confirmed",
    })
    PENDING[42] = ("otp_service", {"order_id": 502})
    bot_client = SimpleNamespace(send_message=AsyncMock())
    context = SimpleNamespace(bot=bot_client)
    user = SimpleNamespace(id=42, username="otpbuyer", full_name="OTP Buyer")

    service_message = SimpleNamespace(text="WhatsApp", reply_text=AsyncMock())
    asyncio.run(handle_pending_input(
        SimpleNamespace(effective_user=user, message=service_message),
        context,
        "en",
    ))

    assert PENDING.get(42) == (
        "otp_country", {"order_id": 502, "service": "WhatsApp"},
    )
    assert "What's the country?" in service_message.reply_text.await_args.args[0]

    country_message = SimpleNamespace(text="Nigeria", reply_text=AsyncMock())
    asyncio.run(handle_pending_input(
        SimpleNamespace(effective_user=user, message=country_message),
        context,
        "en",
    ))

    assert PENDING.get(42) is None
    order = mock_mongodb.orders.find_one({"id": 502})
    assert order["otp_service"] == "WhatsApp"
    assert order["otp_country"] == "Nigeria"
    assert order["otp_workflow_status"] == "sent_to_admin"
    admin_call = bot_client.send_message.await_args
    assert admin_call.args[0] == 999
    assert "New paid OTP request" in admin_call.args[1]
    assert "WhatsApp" in admin_call.args[1]
    assert "Nigeria" in admin_call.args[1]
    assert "3 OTP code(s)" in admin_call.args[1]
    assert "3.00 USDT" in admin_call.args[1]
    assert mock_mongodb.support_tickets.find_one({
        "user_id": 42, "order_id": 502, "category": "otp_order",
    })
    customer_call = country_message.reply_text.await_args
    assert "directly in this bot" in customer_call.args[0]
    assert customer_call.kwargs["reply_markup"].inline_keyboard[0][0].url is None
    assert admin_call.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "adm_deliver:502"


def test_customer_support_text_is_deleted_after_channel_delivery(mock_mongodb):
    PENDING[42] = ("support", "other")
    user = SimpleNamespace(
        id=42,
        full_name="Support Client",
        first_name="Support",
        username="client42",
    )
    message = SimpleNamespace(
        text="I need help",
        reply_text=AsyncMock(),
        delete=AsyncMock(),
    )
    bot_client = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=800)),
    )

    asyncio.run(handle_pending_input(
        SimpleNamespace(effective_user=user, message=message),
        SimpleNamespace(bot=bot_client),
        "en",
    ))

    message.delete.assert_awaited_once()
    assert bot_client.send_message.await_args.args[0] == -1004326329551
    assert "I need help" in bot_client.send_message.await_args.args[1]


def test_customer_can_close_active_support_ticket(monkeypatch, mock_mongodb):
    ticket = support_service.create_ticket(42, "Help", category="other")
    PENDING[42] = ("ticket_message", ticket["id"])
    close_notice = AsyncMock()
    monkeypatch.setattr("bot.support_bridge.send_ticket_closed", close_notice)
    query = SimpleNamespace(
        data=f"ticket_close:{ticket['id']}",
        from_user=SimpleNamespace(id=42),
        message=SimpleNamespace(),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    monkeypatch.setattr("bot.lang_of", lambda _user_id: "en")

    asyncio.run(cb_navigation(
        SimpleNamespace(callback_query=query),
        SimpleNamespace(bot=SimpleNamespace()),
    ))

    assert support_service.get_ticket(ticket["id"])["status"] == "closed"
    assert PENDING.get(42) is None
    query.edit_message_text.assert_awaited_once()
    close_notice.assert_awaited_once()


def test_attachment_can_create_the_first_ticket_message(mock_mongodb):
    PENDING[42] = ("support", "other")
    user = SimpleNamespace(
        id=42,
        full_name="Media Client",
        first_name="Media",
        username="media42",
    )
    message = SimpleNamespace(
        message_id=61,
        chat_id=42,
        chat=SimpleNamespace(id=42),
        caption="See screenshot",
        photo=[SimpleNamespace(file_id="photo")],
        document=None,
        video=None,
        animation=None,
        audio=None,
        voice=None,
        video_note=None,
        sticker=None,
        reply_text=AsyncMock(),
        delete=AsyncMock(),
    )
    bot_client = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=801)),
        copy_message=AsyncMock(return_value=SimpleNamespace(message_id=802)),
    )

    handled = asyncio.run(handle_ticket_attachment(
        SimpleNamespace(effective_user=user, effective_message=message),
        SimpleNamespace(bot=bot_client),
    ))

    assert handled is True
    ticket = mock_mongodb.support_tickets.find_one({"user_id": 42})
    assert ticket["category"] == "other"
    assert PENDING.get(42) == ("ticket_message", ticket["id"])
    message.reply_text.assert_awaited_once()
    message.delete.assert_awaited_once()
    bot_client.copy_message.assert_awaited_once()
