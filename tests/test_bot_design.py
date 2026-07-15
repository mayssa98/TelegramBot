"""Regression tests for the customer-facing Telegram navigation."""

from pathlib import Path

import keyboards as kb
from bot import payment_scanner_frame
from i18n import t


def test_main_menu_is_compact_and_actions_match_labels():
    keyboard = kb.main_menu_keyboard("fr", user_id=42)

    labels = [[button.text for button in row] for row in keyboard.keyboard[:3]]
    assert labels == [
        [t("fr", "menu_catalog"), t("fr", "menu_orders")],
        [t("fr", "menu_account"), t("fr", "menu_affiliate")],
        [t("fr", "menu_support"), t("fr", "menu_help")],
    ]
    assert "compte" in t("fr", "menu_account").lower()
    assert "aide" in t("fr", "menu_help").lower()


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

    assert {"catalog", "orders", "account", "affiliate", "support", "help", "language"} <= callbacks


def test_onboarding_has_three_steps_and_catalog_cta():
    assert kb.onboarding_keyboard("fr", 1).inline_keyboard[0][0].callback_data == "tour:2"
    assert kb.onboarding_keyboard("fr", 2).inline_keyboard[0][0].callback_data == "tour:3"
    assert kb.onboarding_keyboard("fr", 3).inline_keyboard[0][0].callback_data == "catalog"


def test_welcome_banner_is_packaged_with_the_bot():
    banner = Path(__file__).resolve().parents[1] / "assets" / "blackmarket-welcome-v2.png"

    assert banner.exists()
    assert banner.stat().st_size > 100_000
