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
    assert "Order ID" in message
    assert "Vérifier avec TXID" in message
    assert "Mémo" not in message
    assert "Produit : *Gemini AI Pro 18m*" in message
    assert "ENVOYEZ EXACTEMENT : 0.65 USDT" in message
    assert "Binance ID : `904169573`" in message
    assert "Commande : *#6074*" in message


def test_bybit_payment_message_uses_uid_and_receipt_txid():
    message = t(
        "fr", "bybit_order_created", oid=6075, service="AI",
        offer="Lovable", qty=1, total="12.00", cur="USDT",
        bybit_uid="545988761",
    )

    assert "*Bybit Pay*" in message
    assert "UID Bybit : `545988761`" in message
    assert "12.00 USDT" in message
    assert "TXID" in t("fr", "ask_bybit_txid", oid=6075)


def test_topup_failure_hides_internal_binance_error():
    message = t("en", "topup_failed")

    assert "temporarily unavailable" in message
    assert "HTTP" not in message
    assert "451" not in message
    assert "Copier Binance ID" in t("fr", "btn_copy_binance_id")
    assert "Copier le montant exact" in t("fr", "btn_copy_amount")
    assert "`904169573`" in t("fr", "copy_binance_id_msg", binance_id="904169573")
    assert "TXID" in t("fr", "verifying")
    assert "capture du paiement" in t("fr", "payment_contact_admin", oid=6074)


def test_already_confirmed_topup_has_a_clear_customer_message():
    message = t("en", "topup_already_confirmed")

    assert "already confirmed" in message
    assert "already verified and credited" in message
    assert "not been credited again" in message


def test_french_quantity_prompt_mentions_stock_limit():
    message = t("fr", "choose_quantity", offer="Chat GPT Plus", stock=9, price="1.23", cur="USDT")

    assert "Entrez la quantité" in message
    assert "1-9" in message
    assert "Stock disponible : *9*" in message
    assert "1.23 USDT" in message


def test_admin_text_prompt_formats_text_key_without_argument_collision():
    message = t(
        "fr", "admin_send_new_text",
        text_key="btn_pay_wallet", selected_lang="fr", current="Payer avec mon solde",
    )
    assert "btn_pay_wallet" in message
    assert "Payer avec mon solde" in message


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


def test_announcement_templates_include_product_catalog_period_and_warranty():
    for key in ("channel_stock_announcement", "offer_stock_announcement", "flash_sale_announcement"):
        for lang in ("fr", "en", "ar"):
            msg = t(
                lang,
                key,
                emoji="🍿",
                service="Streaming VOD",
                offer="Netflix 4K Ultra",
                period="30 j" if lang == "fr" else "30 days",
                warranty="NW",
                price="4.99",
                cur="USDT",
                stock=10,
                added=5,
                old_price="7.99",
                discount=38,
                remaining="2h 15m",
            )
            assert "Streaming VOD" in msg
            assert "Netflix 4K Ultra" in msg
            assert ("30 j" if lang == "fr" else "30 days") in msg
            assert "NW" in msg
