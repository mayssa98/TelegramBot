"""Tests for translated bot copy."""

from i18n import t


def test_french_welcome_message_is_professional():
    message = t("fr", "welcome", shop="BlackMarket")

    assert "Bienvenue sur BlackMarket" in message
    assert "services numériques premium" in message
    assert "Informations claires et service fiable" in message
    assert "Assistance dédiée" in message
    assert "Choisissez votre espace" in message
    assert "Binance" not in message
    assert "paiement" not in message.lower()


def test_french_payment_message_matches_binance_style():
    message = t(
        "fr",
        "order_created",
        oid=6074,
        service="AI",
        offer="Gemini AI Pro 18m",
        qty=1,
        total="0.65",
        cur="USDT",
        binance_id="904169573",
    )

    assert "*Binance Pay*" in message
    assert "Auto-check activé" in message
    assert "Produit : *Gemini AI Pro 18m*" in message
    assert "ENVOYEZ EXACTEMENT : 0.65 USDT" in message
    assert "Binance ID : `904169573`" in message
    assert "Payment ID : *#6074*" in message
    assert "Copier Binance ID" in t("fr", "btn_copy_binance_id")
    assert "Copier le montant exact" in t("fr", "btn_copy_amount")
    assert "`904169573`" in t("fr", "copy_binance_id_msg", binance_id="904169573")
    assert "15 secondes" in t("fr", "auto_check_started", seconds=15)
    assert "ID de transaction Binance" in t("fr", "auto_check_timeout", oid=6074)
    assert "capture du paiement" in t("fr", "payment_contact_admin", oid=6074)


def test_french_quantity_prompt_mentions_stock_limit():
    message = t("fr", "choose_quantity", offer="Chat GPT Plus", stock=9, price="1.23", cur="USDT")

    assert "Choisissez la quantité" in message
    assert "Stock disponible : *9*" in message
    assert "1.23 USDT" in message


def test_offer_detail_template_has_premium_sections():
    message = t(
        "fr",
        "offer_detail",
        emoji="🌀",
        service="Chat GPT",
        offer="Chat GPT Plus",
        price="4.50",
        cur="USDT",
        stock=5,
        note="Full",
        duration="30 Days",
        mail="iCloud",
        access="Ready-made account",
        delivery="Instantané",
        description="• Premium tools",
    )

    assert "*Warranty*" in message
    assert "*Duration*" in message
    assert "*Mail*" in message
    assert "*Access*" in message
