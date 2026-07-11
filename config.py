"""
Configuration centrale du bot HEAVENPREM.
Toutes les valeurs sensibles peuvent être surchargées par des variables d'environnement,
ce qui facilite le déploiement sur un hébergement 24/7 sans modifier le code.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---
BOT_TOKEN = os.environ.get(
    "HP_BOT_TOKEN",
    "",
)

# Identifiant Telegram de l'administrateur (panneau admin + notifications)
ADMIN_ID = int(os.environ.get("HP_ADMIN_ID", "5141968904"))

# --- Paiement Binance Pay ---
BINANCE_PAY_ID = os.environ.get("HP_BINANCE_PAY_ID", "454813844")

# --- Vérification automatique via Gmail (API Manus) ---
# Compte Gmail recevant les notifications Binance
GMAIL_ACCOUNT = os.environ.get("HP_GMAIL_ACCOUNT", "anwerrmili2@gmail.com")
# Clé API Manus : nécessaire pour la vérification automatique des paiements.
# Si vide -> repli automatique en validation manuelle admin (jamais de blocage).
MANUS_API_KEY = os.environ.get("HP_MANUS_API_KEY", "").strip()
MANUS_API_BASE = os.environ.get("HP_MANUS_API_BASE", "https://api.manus.ai")
# UUID du connecteur Gmail dans Manus
GMAIL_CONNECTOR_UID = os.environ.get(
    "HP_GMAIL_CONNECTOR_UID", "9444d960-ab7e-450f-9cb9-b9467fb0adda"
)

# --- Base de données ---
MONGODB_URI = os.environ.get("HP_MONGODB_URI", "").strip()
MONGODB_DB = os.environ.get("HP_MONGODB_DB", "heavenprem").strip()
INVENTORY_KEY = os.environ.get("HP_INVENTORY_KEY", "").strip()
DASHBOARD_PASSWORD = os.environ.get("HP_DASHBOARD_PASSWORD", "").strip()

# --- Divers ---
SHOP_NAME = "HEAVENPREM"
DEFAULT_LANG = "fr"
SUPPORTED_LANGS = ["fr", "en", "ar"]
CURRENCY = "$"
AFFILIATE_TARGET = int(os.environ.get("HP_AFFILIATE_TARGET", "10"))
AFFILIATE_REWARD_CENTS = int(os.environ.get("HP_AFFILIATE_REWARD_CENTS", "100"))

# --- Binance API (historique Binance Pay, lecture seule) ---
# Ne jamais placer les clés directement dans ce fichier.
BINANCE_API_KEY = os.environ.get("HP_BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET = os.environ.get("HP_BINANCE_API_SECRET", "").strip()
BINANCE_API_BASE = os.environ.get("HP_BINANCE_API_BASE", "https://api.binance.com").rstrip("/")
PAY_CURRENCY = os.environ.get("HP_PAY_CURRENCY", "USDT").upper().strip()

# Délai (secondes) max d'attente d'une vérification automatique avant repli manuel
VERIFY_TIMEOUT = int(os.environ.get("HP_VERIFY_TIMEOUT", "120"))
