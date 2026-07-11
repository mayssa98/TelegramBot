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

# ---------------------------------------------------------------------------
# Paiement Binance Pay
# ---------------------------------------------------------------------------
BINANCE_PAY_ID: str = os.environ.get("HP_BINANCE_PAY_ID", "")

# ---------------------------------------------------------------------------
# Vérification automatique via Binance API (lecture seule)
# ---------------------------------------------------------------------------
BINANCE_API_KEY: str = os.environ.get("HP_BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET: str = os.environ.get("HP_BINANCE_API_SECRET", "").strip()
BINANCE_API_BASE: str = os.environ.get(
    "HP_BINANCE_API_BASE", "https://api.binance.com"
).rstrip("/")
PAY_CURRENCY: str = os.environ.get("HP_PAY_CURRENCY", "USDT").upper().strip()

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
DEFAULT_LANG: str = "fr"
SUPPORTED_LANGS: list[str] = ["fr", "en", "ar"]
CURRENCY: str = "USDT"

# ---------------------------------------------------------------------------
# Affiliation
# ---------------------------------------------------------------------------
AFFILIATE_TARGET: int = int(os.environ.get("HP_AFFILIATE_TARGET", "10"))
AFFILIATE_REWARD_CENTS: int = int(os.environ.get("HP_AFFILIATE_REWARD_CENTS", "100"))

# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------
ORDER_EXPIRY_SECONDS: int = int(os.environ.get("HP_ORDER_EXPIRY_SECONDS", "1800"))
LOW_STOCK_THRESHOLD: int = int(os.environ.get("HP_LOW_STOCK_THRESHOLD", "5"))

# Délai (secondes) max d'attente d'une vérification automatique avant repli manuel.
VERIFY_TIMEOUT: int = int(os.environ.get("HP_VERIFY_TIMEOUT", "120"))
