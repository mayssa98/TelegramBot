"""Tests for Telegram keyboard labels."""

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

    assert keyboard.inline_keyboard[0][0].callback_data == "confirm_buy:9:4"


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

    assert label == "\U0001f7e9 SuperGrok 12 Months | Full Warranty | $30.00 | \U0001f4e6 12"


def test_offer_button_label_uses_yellow_for_low_stock():
    label = offer_button_label(
        "en",
        {
            "name": "Low Stock Product",
            "note": "Full Warranty",
            "price": 5.0,
            "stock": 2,
        },
    )

    assert label.startswith("\U0001f7e8 Low Stock Product")


def test_stock_badge_uses_the_same_thresholds_for_services_and_offers():
    assert stock_badge(11) == "🟩"
    assert stock_badge(10) == "🟨"
    assert stock_badge(1) == "🟨"
    assert stock_badge(0) == "🟥"
    assert stock_button_style(11) == "success"
    assert stock_button_style(10) is None
    assert stock_button_style(1) is None
    assert stock_button_style(0) == "danger"


def test_services_keyboard_uses_total_stock_color(monkeypatch):
    services = [
        {"id": 1, "name": "Large", "emoji": "📦"},
        {"id": 2, "name": "Low", "emoji": "📦"},
        {"id": 3, "name": "Empty", "emoji": "📦"},
    ]
    totals = {1: 11, 2: 7, 3: 0}
    monkeypatch.setattr(kb.db, "list_services", lambda: services)
    monkeypatch.setattr(kb.db, "service_total_stock", lambda service_id: totals[service_id])

    keyboard = kb.services_keyboard("fr")
    labels = [
        button.text
        for row in keyboard.inline_keyboard[:-1]
        for button in row
    ]

    assert labels[0].startswith("🟩")
    assert labels[1].startswith("🟨")
    assert labels[2].startswith("🟥")
    assert keyboard.inline_keyboard[0][0].style == "success"
    assert keyboard.inline_keyboard[0][1].style is None
    assert keyboard.inline_keyboard[1][0].style == "danger"


def test_offer_buttons_use_native_telegram_styles(monkeypatch):
    monkeypatch.setattr(kb.db, "list_offers", lambda _service_id: [
        {"id": 1, "name": "Large", "price": 10.0, "stock": 12, "note": ""},
        {"id": 2, "name": "Low", "price": 10.0, "stock": 5, "note": ""},
        {"id": 3, "name": "Empty", "price": 10.0, "stock": 0, "note": ""},
    ])

    keyboard = kb.offers_keyboard("en", 1)

    assert keyboard.inline_keyboard[0][0].style == "success"
    assert keyboard.inline_keyboard[1][0].style is None
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

    assert label.startswith("\U0001f7e5 Very Long Product Name With Man...")
    assert label.endswith("| Full Warranty | $2.50 | \U0001f534 0 manual")
