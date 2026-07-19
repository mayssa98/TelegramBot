"""Tests for Telegram keyboard labels."""

import admin
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


def test_quantity_confirmation_keeps_selected_quantity():
    keyboard = kb.confirm_buy_keyboard("fr", 9, 4)

    assert keyboard.inline_keyboard[0][0].callback_data == "pay_wallet:9:4"
    assert keyboard.inline_keyboard[1][0].callback_data == "pay_binance:9:4"


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

    assert label == "SuperGrok 12 Months | Stock: 12"


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

    assert label == "Low Stock Product | Stock: 2"


def test_offer_button_always_keeps_live_stock_visible_with_long_name():
    label = offer_button_label("en", {"name": "A" * 100, "stock": 35})

    assert label.endswith("| Stock: 35")
    assert len(label) <= 64


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

    assert label.endswith("| Stock: 0")
    assert len(label) <= 64


def test_offer_button_uses_admin_selected_animated_emoji(monkeypatch):
    monkeypatch.setattr(kb.db, "list_offers", lambda _service_id: [{
        "id": 8,
        "name": "Premium",
        "stock": 2,
        "custom_emoji_id": "admin-selected-id",
    }])

    button = kb.offers_keyboard("en", 1).inline_keyboard[0][0]

    assert button.text == "Premium | Stock: 2"
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
    assert "adm_inventory:4" in callbacks


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
