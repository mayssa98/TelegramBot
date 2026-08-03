"""
Configuration centrale du bot HEAVENPREM.
Toutes les valeurs sensibles sont lues depuis les variables d'environnement.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
BOT_TOKEN: str = os.environ.get("HP_BOT_TOKEN", "")

ADMIN_ID: int = int(os.environ.get("HP_ADMIN_ID", "0"))
ADMIN_USERNAME: str = os.environ.get("HP_ADMIN_USERNAME", "@Anwer_07").strip()
REQUIRED_CHANNEL: str = os.environ.get("HP_REQUIRED_CHANNEL", "@blackmarketBotChannel").strip()
REQUIRED_GROUP: str = os.environ.get("HP_REQUIRED_GROUP", "@Blackmarketgrp").strip()

# ---------------------------------------------------------------------------
# Paiement Binance Pay
# ---------------------------------------------------------------------------
BINANCE_PAY_ID: str = os.environ.get("HP_BINANCE_PAY_ID", "")
USDT_EVM_ADDRESS: str = os.environ.get(
    "HP_USDT_EVM_ADDRESS",
    "0x6529804d712d5ef4bef5c60af4a3683bd7300411",
).strip()

# ---------------------------------------------------------------------------
# Vérification automatique via Binance API (lecture seule)
# ---------------------------------------------------------------------------
BINANCE_API_KEY: str = os.environ.get("HP_BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET: str = os.environ.get("HP_BINANCE_API_SECRET", "").strip()
BINANCE_API_BASE: str = os.environ.get(
    "HP_BINANCE_API_BASE", "https://api.binance.com"
).rstrip("/")

# ---------------------------------------------------------------------------
# Fournisseur revendeur MailReader
# ---------------------------------------------------------------------------
MAILREADER_API_KEY: str = os.environ.get("HP_MAILREADER_API_KEY", "").strip()
MAILREADER_API_BASE: str = os.environ.get(
    "HP_MAILREADER_API_BASE", "https://api.mailreader.tech"
).rstrip("/")

# ---------------------------------------------------------------------------
# Fournisseur revendeur Shamekh's bot
# ---------------------------------------------------------------------------
SHAMEKH_API_KEY: str = os.environ.get("HP_SHAMEKH_API_KEY", "").strip()
SHAMEKH_API_BASE: str = os.environ.get(
    "HP_SHAMEKH_API_BASE", "https://worker-production-53ca.up.railway.app"
).rstrip("/")

# ---------------------------------------------------------------------------
# Fournisseur revendeur Kakao Shop
# ---------------------------------------------------------------------------
KAKAO_API_KEY: str = os.environ.get("HP_KAKAO_API_KEY", "").strip()
KAKAO_API_BASE: str = os.environ.get(
    "HP_KAKAO_API_BASE", "https://api.shopdigital.app"
).rstrip("/")

# ---------------------------------------------------------------------------
# Fournisseur revendeur VEX Reseller
# ---------------------------------------------------------------------------
VEX_API_KEY: str = os.environ.get("HP_VEX_API_KEY", "").strip()
VEX_API_BASE: str = os.environ.get(
    "HP_VEX_API_BASE",
    "https://eismrrkygprctnwxmkbw.supabase.co/functions/v1/reseller-api",
).rstrip("/")
_BINANCE_OFFICIAL_BASES = (
    "https://api.binance.com",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
)
BINANCE_API_BASES: tuple[str, ...] = tuple(dict.fromkeys(
    [
        BINANCE_API_BASE,
        *[
            value.strip().rstrip("/")
            for value in os.environ.get("HP_BINANCE_API_BASES", "").split(",")
            if value.strip()
        ],
        *_BINANCE_OFFICIAL_BASES,
    ]
))
PAY_CURRENCY: str = os.environ.get("HP_PAY_CURRENCY", "USDT").upper().strip()
TEST_PAYMENT_ENABLED: bool = os.environ.get(
    "HP_TEST_PAYMENT_ENABLED", "false"
).strip().lower() in {"1", "true", "yes", "on"}

# ---------------------------------------------------------------------------
# Vérification via Gmail / Manus (optionnel)
# ---------------------------------------------------------------------------
GMAIL_ACCOUNT: str = os.environ.get("HP_GMAIL_ACCOUNT", "")
MANUS_API_KEY: str = os.environ.get("HP_MANUS_API_KEY", "").strip()
MANUS_API_BASE: str = os.environ.get("HP_MANUS_API_BASE", "https://api.manus.ai")
GMAIL_CONNECTOR_UID: str = os.environ.get("HP_GMAIL_CONNECTOR_UID", "")

# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------
MONGODB_URI: str = os.environ.get("HP_MONGODB_URI", "").strip()
MONGODB_DB: str = os.environ.get("HP_MONGODB_DB", "heavenprem").strip()
INVENTORY_KEY: str = os.environ.get("HP_INVENTORY_KEY", "").strip()
DASHBOARD_PASSWORD: str = os.environ.get("HP_DASHBOARD_PASSWORD", "").strip()

# ---------------------------------------------------------------------------
# Boutique
# ---------------------------------------------------------------------------
SHOP_NAME: str = os.environ.get("HP_SHOP_NAME", "BlackMarket").strip()
DEFAULT_LANG: str = "en"
SUPPORTED_LANGS: list[str] = ["en"]
CURRENCY: str = "USDT"

# ---------------------------------------------------------------------------
# Affiliation
# ---------------------------------------------------------------------------
AFFILIATE_QUALIFY_CENTS: int = int(os.environ.get("HP_AFFILIATE_QUALIFY_CENTS", "1000"))
AFFILIATE_FIVE_REWARD_CENTS: int = int(os.environ.get("HP_AFFILIATE_FIVE_REWARD_CENTS", "500"))
AFFILIATE_TEN_REWARD_CENTS: int = int(os.environ.get("HP_AFFILIATE_TEN_REWARD_CENTS", "200"))
AFFILIATE_DAILY_CAP: int = int(os.environ.get("HP_AFFILIATE_DAILY_CAP", "10"))
AFFILIATE_MIN_PURCHASE_CENTS: int = int(os.environ.get("HP_AFFILIATE_MIN_PURCHASE_CENTS", "100"))

# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------
ORDER_EXPIRY_SECONDS: int = int(os.environ.get("HP_ORDER_EXPIRY_SECONDS", "1800"))
LOW_STOCK_THRESHOLD: int = int(os.environ.get("HP_LOW_STOCK_THRESHOLD", "5"))

# Délai (secondes) max d'attente d'une vérification automatique avant repli manuel.
VERIFY_TIMEOUT: int = int(os.environ.get("HP_VERIFY_TIMEOUT", "120"))


def configuration_issues(*, webhook: bool = False, inventory: bool = False) -> list[str]:
    """Return actionable configuration problems without exposing secret values."""
    required = {
        "HP_BOT_TOKEN": BOT_TOKEN,
        "HP_ADMIN_ID": ADMIN_ID,
        "HP_MONGODB_URI": MONGODB_URI,
    }
    if inventory:
        required["HP_INVENTORY_KEY"] = INVENTORY_KEY
    if webhook:
        required.update({
            "HP_WEBHOOK_SECRET": os.environ.get("HP_WEBHOOK_SECRET", "").strip(),
            "HP_DASHBOARD_PASSWORD": DASHBOARD_PASSWORD,
        })
    return [name for name, value in required.items() if not value]
