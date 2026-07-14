"""Tests for Telegram keyboard labels."""

import keyboards as kb
from keyboards import offer_button_label


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


def test_main_menu_uses_store_layout():
    keyboard = kb.main_menu_keyboard("en", user_id=0)
    rows = [[button.text for button in row] for row in keyboard.keyboard]

    assert rows[0] == ["🎯 Shop"]
    assert rows[1] == ["📱 Virtual Numbers"]
    assert rows[2] == ["🟡 History", "⚡ Settings"]
    assert rows[3] == ["🛎️ Support", "🔗 API LINK"]
    assert rows[4] == ["🌐 Language"]


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
