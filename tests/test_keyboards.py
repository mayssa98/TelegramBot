"""Tests for Telegram keyboard labels."""

import admin
import database as db
import keyboards as kb
from keyboards import offer_button_label, stock_badge, stock_button_style


def test_quantity_keyboard_uses_stock_as_maximum():
    keyboard = kb.quantity_keyboard("fr", {"id": 9, "stock": 7})

    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]

    assert "buyq:9:1" in callbacks
    assert "buyq:9:7" in callbacks
    assert "buyq:9:8" not in callbacks


def test_delivery_offers_admin_account_collection_with_order_id(monkeypatch):
    monkeypatch.setattr("keyboards.ADMIN_USERNAME", "@Anwer_07")

    keyboard = kb.post_delivery_keyboard("en", 6074)
    button = keyboard.inline_keyboard[0][0]

    assert "@Anwer_07" in button.text
    assert button.url.startswith("https://t.me/Anwer_07?text=")
    assert "6074" in button.url


def test_quantity_confirmation_keeps_selected_quantity():
    keyboard = kb.confirm_buy_keyboard("fr", 9, 4)

    assert keyboard.inline_keyboard[0][0].callback_data == "pay_wallet:9:4"
    assert keyboard.inline_keyboard[1][0].callback_data == "pay_binance:9:4"
    assert keyboard.inline_keyboard[2][0].callback_data == "pay_bsc:9:4"
    assert keyboard.inline_keyboard[3][0].callback_data == "pay_polygon:9:4"


def test_onchain_payment_keyboard_submits_txid_without_auto_confirmation():
    keyboard = kb.onchain_payment_keyboard("en", 81)

    assert keyboard.inline_keyboard[0][0].callback_data == "paid_chain:81"
    assert keyboard.inline_keyboard[1][0].callback_data == "cancel_buy:81"


def test_offer_button_label_uses_store_style():
    label = offer_button_label(
        "en",
        {
            "name": "SuperGrok 12 Months",
            "note": "Full Warranty",
            "price": 30.0,
            "stock": 12,
        },
    )

    assert label == "SuperGrok 12 Months | $30 | Stock: 12"


def test_offer_button_label_uses_sky_blue_for_low_stock():
    label = offer_button_label(
        "en",
        {
            "name": "Low Stock Product",
            "note": "Full Warranty",
            "price": 5.0,
            "stock": 2,
        },
    )

    assert label == "Low Stock Product | $5 | Stock: 2"


def test_offer_button_keeps_non_dollar_currency_visible():
    label = offer_button_label(
        "en",
        {"name": "European plan", "price": 4.5, "currency": "EUR", "stock": 3},
    )

    assert label == "European plan | 4.5 EUR | Stock: 3"


def test_offer_button_always_keeps_price_and_live_stock_visible_with_long_name():
    label = offer_button_label(
        "en", {"name": "A" * 100, "price": 2.5, "stock": 35},
    )

    assert label.endswith("| $2.5 | Stock: 35")
    assert len(label) <= 64


def test_unlimited_offer_displays_infinity_and_remains_buyable():
    offer = {
        "id": 9, "service_id": 1, "name": "Managed accounts",
        "price": 5.0, "stock": 0, "unlimited_stock": True,
    }

    assert "Stock: ∞" in offer_button_label("en", offer)
    callbacks = [
        button.callback_data
        for row in kb.offer_detail_keyboard("en", offer).inline_keyboard
        for button in row
    ]
    assert "buy:9" in callbacks
    assert "catalog" in callbacks


def test_stock_label_is_listed_in_catalog_admin_category():
    assert admin.text_category_for_key("stock_label") == "catalog"


def test_stock_label_accepts_admin_premium_emoji(monkeypatch):
    monkeypatch.setattr(kb.db, "list_offers", lambda _service_id: [{
        "id": 8, "name": "Premium", "stock": 2, "custom_emoji_id": "offer-icon",
    }])
    monkeypatch.setattr(
        kb.db,
        "get_text_override_icon",
        lambda key, lang: "premium-stock-icon" if key == "stock_label" else "",
    )

    button = kb.offers_keyboard("en", 1).inline_keyboard[0][0]

    assert button.icon_custom_emoji_id == "premium-stock-icon"


def test_stock_badge_uses_the_same_thresholds_for_services_and_offers():
    assert stock_badge(4) == "🟩"
    assert stock_badge(3) == "🟦"
    assert stock_badge(2) == "🟦"
    assert stock_badge(1) == "🟦"
    assert stock_badge(0) == "🟥"
    assert stock_button_style(4) == "success"
    assert stock_button_style(3) == "primary"
    assert stock_button_style(2) == "primary"
    assert stock_button_style(1) == "primary"
    assert stock_button_style(0) == "danger"


def test_services_keyboard_uses_total_stock_color(monkeypatch):
    services = [
        {"id": 1, "name": "Large", "emoji": "📦"},
        {"id": 2, "name": "Low", "emoji": "📦"},
        {"id": 3, "name": "Empty", "emoji": "📦"},
    ]
    services[0]["total_stock"] = 4
    services[1]["total_stock"] = 3
    services[2]["total_stock"] = 0
    monkeypatch.setattr(kb.db, "list_services_with_stock", lambda: services)

    keyboard = kb.services_keyboard("fr")
    labels = [
        button.text
        for row in keyboard.inline_keyboard[:-2]
        for button in row
    ]

    assert labels == ["Large", "Low", "Empty"]
    assert keyboard.inline_keyboard[0][0].style == "success"
    assert keyboard.inline_keyboard[0][1].style == "primary"
    assert keyboard.inline_keyboard[1][0].style == "danger"


def test_offer_buttons_use_native_telegram_styles(monkeypatch):
    monkeypatch.setattr(kb.db, "list_offers", lambda _service_id: [
        {"id": 1, "name": "Large", "price": 10.0, "stock": 4, "note": ""},
        {"id": 2, "name": "Low", "price": 10.0, "stock": 3, "note": ""},
        {"id": 3, "name": "Empty", "price": 10.0, "stock": 0, "note": ""},
    ])

    keyboard = kb.offers_keyboard("en", 1)

    assert keyboard.inline_keyboard[0][0].style == "success"
    assert keyboard.inline_keyboard[1][0].style == "primary"
    assert keyboard.inline_keyboard[2][0].style == "danger"


def test_orders_services_keyboard_matches_grouped_design():
    keyboard = kb.orders_services_keyboard("en", [
        {"name": "ChatGPT", "emoji": "🤖", "count": 6},
        {"name": "Gemini", "emoji": "💡", "count": 2},
    ], total=8)

    assert keyboard.inline_keyboard[0][0].text == "🤖 ChatGPT (6)"
    assert keyboard.inline_keyboard[0][0].callback_data == "orders_group:0"
    assert keyboard.inline_keyboard[2][0].text == "📊 All Orders (8)"
    assert keyboard.inline_keyboard[-1][0].callback_data == "home"


def test_offer_button_label_truncates_long_names():
    label = offer_button_label(
        "en",
        {
            "name": "Very Long Product Name With Many Details And Devices",
            "note": "",
            "price": 2.5,
            "stock": 0,
        },
    )

    assert label.endswith("| $2.5 | Stock: 0")
    assert len(label) <= 64


def test_offer_button_uses_admin_selected_animated_emoji(monkeypatch):
    monkeypatch.setattr(kb.db, "list_offers", lambda _service_id: [{
        "id": 8,
        "name": "Premium",
        "price": 5,
        "stock": 2,
        "custom_emoji_id": "admin-selected-id",
    }])

    button = kb.offers_keyboard("en", 1).inline_keyboard[0][0]

    assert button.text == "Premium | $5 | Stock: 2"
    assert button.icon_custom_emoji_id == "admin-selected-id"


def test_service_button_uses_admin_selected_animated_emoji(monkeypatch):
    monkeypatch.setattr(kb.db, "list_services_with_stock", lambda: [{
        "id": 3,
        "name": "Streaming",
        "total_stock": 8,
        "custom_emoji_id": "premium-service-emoji",
    }])

    button = kb.services_keyboard("en").inline_keyboard[0][0]

    assert button.text == "Streaming"
    assert button.icon_custom_emoji_id == "premium-service-emoji"


def test_admin_catalog_button_uses_premium_emoji(monkeypatch):
    monkeypatch.setattr(admin.db, "list_services", lambda active_only=False: [{
        "id": 4,
        "name": "Chat GPT",
        "active": 1,
        "custom_emoji_id": "admin-premium-id",
    }])

    button = admin.catalog_admin_keyboard().inline_keyboard[0][0]

    assert button.text == "Chat GPT"
    assert button.icon_custom_emoji_id == "admin-premium-id"


def test_admin_cannot_manually_modify_offer_stock(monkeypatch):
    monkeypatch.setattr(admin.db, "get_offer", lambda _offer_id: {
        "id": 4, "service_id": 1, "active": 1,
    })

    keyboard = admin.offer_admin_keyboard(4)
    callbacks = {
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    }

    assert not any(value and value.startswith("adm_setstock:") for value in callbacks)


def test_admin_offer_panel_can_broadcast_current_price_and_stock(monkeypatch):
    monkeypatch.setattr(
        admin.db,
        "get_offer",
        lambda _offer_id: {
            "id": 4, "service_id": 1, "active": 1,
            "unlimited_stock": False,
        },
    )

    callbacks = [
        button.callback_data
        for row in admin.offer_admin_keyboard(4).inline_keyboard
        for button in row
    ]

    assert "adm_broadcast_offer:4" in callbacks
    assert "adm_inventory:4" in callbacks


def test_admin_offer_panel_can_start_and_stop_flash_sale(monkeypatch):
    offer = {
        "id": 4, "service_id": 1, "active": 1,
        "unlimited_stock": False, "flash_sale_active": False,
    }
    monkeypatch.setattr(admin.db, "get_offer", lambda _offer_id: offer)
    callbacks = {
        button.callback_data
        for row in admin.offer_admin_keyboard(4).inline_keyboard
        for button in row
    }
    assert "adm_flash_start:4" in callbacks

    offer["flash_sale_active"] = True
    callbacks = {
        button.callback_data
        for row in admin.offer_admin_keyboard(4).inline_keyboard
        for button in row
    }
    assert "adm_flash_stop:4" in callbacks


def test_admin_panel_has_custom_announcement_button():
    callbacks = [
        button.callback_data
        for row in admin.admin_panel_keyboard().inline_keyboard
        for button in row
    ]

    assert "adm_broadcast_message" in callbacks


def test_home_menu_offers_optional_channel_and_group_links(mock_mongodb):
    keyboard = kb.home_keyboard("en", 42)
    urls = {
        button.url
        for row in keyboard.inline_keyboard
        for button in row
        if button.url
    }

    assert "https://t.me/blackmarketBotChannel" in urls
    assert "https://t.me/Blackmarketgrp" in urls


def test_admin_panel_has_persistent_maintenance_toggle(mock_mongodb):
    keyboard = admin.admin_panel_keyboard()
    button = next(
        button
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data == "adm_maintenance_toggle"
    )
    assert "OFF" in button.text

    db.set_setting("maintenance_enabled", True)
    keyboard = admin.admin_panel_keyboard()
    button = next(
        button
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data == "adm_maintenance_toggle"
    )
    assert "ON" in button.text


def test_admin_panel_has_user_activity_option(mock_mongodb):
    callbacks = {
        button.callback_data
        for row in admin.admin_panel_keyboard().inline_keyboard
        for button in row
    }

    assert "adm_user_activity" in callbacks
    assert [
        row[0].callback_data
        for row in admin.user_activity_keyboard().inline_keyboard
    ] == ["adm_user_activity", "adm_panel"]


def test_catalog_never_builds_an_empty_button(monkeypatch):
    monkeypatch.setattr(kb.db, "list_services_with_stock", lambda: [{
        "id": 12,
        "name": "✅",
        "total_stock": 0,
    }])

    button = kb.services_keyboard("fr").inline_keyboard[0][0]

    assert button.text == "Service #12"


def test_offers_keyboard_matches_reference_flow(monkeypatch):
    monkeypatch.setattr(kb.db, "list_offers", lambda _service_id: [
        {"id": 1, "name": "Available plan", "price": 10.0, "stock": 14, "note": ""},
        {"id": 2, "name": "Low stock plan", "price": 10.0, "stock": 4, "note": ""},
        {"id": 3, "name": "Unavailable plan", "price": 10.0, "stock": 0, "note": ""},
    ])

    keyboard = kb.offers_keyboard("en", 7)

    assert [row[0].callback_data for row in keyboard.inline_keyboard] == [
        "off:1",
        "off:2",
        "off:3",
        "catalog",
    ]
    assert len(keyboard.inline_keyboard) == 4
def test_admin_text_browser_exposes_every_translation_key():
    from i18n import TRANSLATIONS

    callbacks = []
    page_size = 8
    total_pages = max(1, (len(TRANSLATIONS) + page_size - 1) // page_size)
    for page in range(total_pages):
        keyboard = admin.texts_editor_keyboard(page, page_size=page_size)
        callbacks.extend(
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data and button.callback_data.startswith("adm_text_key:")
        )
    assert {value.split(":", 1)[1] for value in callbacks} == set(TRANSLATIONS)
    assert "adm_text_key:order_created" in callbacks


def test_flat_catalog_keyboard_contains_only_offer_callbacks(monkeypatch):
    monkeypatch.setattr(kb.db, "list_catalog_offers", lambda: [
        {"id": 11, "name": "ChatGPT Plus", "price": 5.0, "stock": 8},
        {"id": 12, "name": "Netflix Premium", "price": 4.0, "stock": 3},
    ])

    keyboard = kb.catalog_offers_keyboard("en")
    product_callbacks = [
        row[0].callback_data for row in keyboard.inline_keyboard[:-2]
    ]

    assert product_callbacks == ["off:11", "off:12"]
    assert all(not callback.startswith("svc:") for callback in product_callbacks)
