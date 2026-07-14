"""Tests for translated bot copy."""

from i18n import t


def test_french_welcome_message_is_professional():
    message = t("fr", "welcome", shop="BlackMarket")

    assert "Bienvenue sur *BlackMarket*" in message
    assert "services numériques fiables" in message
    assert "Paiement sécurisé via Binance Pay" in message
    assert "Livraison rapide après confirmation" in message
    assert "Choisissez une option ci-dessous" in message
