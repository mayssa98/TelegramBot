"""Constructeurs de claviers inline et reply."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
import database as db
from i18n import t
from config import ADMIN_ID, CURRENCY


def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang:fr")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang:ar")],
    ])


def main_menu_keyboard(lang, user_id):
    rows = [
        [t(lang, "menu_catalog")],
        [t(lang, "menu_orders"), t(lang, "menu_help")],
        [t(lang, "menu_affiliate")],
        [t(lang, "menu_lang")],
    ]
    if user_id == ADMIN_ID:
        rows.append([t(lang, "menu_admin")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def services_keyboard(lang):
    buttons = []
    services = db.list_services()
    
    # Grouper par catégorie
    categories = {}
    for svc in services:
        cat = svc.get("category") or t(lang, "cat_other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(svc)
    
    for cat, svcs in categories.items():
        # Titre de la catégorie (bouton non cliquable ou simplement décoratif)
        buttons.append([InlineKeyboardButton(f"─── {cat} ───", callback_data="none")])
        
        # Services par ligne (2 par ligne pour un design plus compact et pro)
        row = []
        for i, svc in enumerate(svcs):
            total = db.service_total_stock(svc["id"])
            label = f"{svc['emoji']} {svc['name']}"
            row.append(InlineKeyboardButton(label, callback_data=f"svc:{svc['id']}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
    buttons.append([InlineKeyboardButton(t(lang, "btn_main_menu"), callback_data="home")])
    return InlineKeyboardMarkup(buttons)


def offers_keyboard(lang, service_id):
    buttons = []
    for off in db.list_offers(service_id):
        if off["price"] is None:
            price_str = t(lang, "price_tbd")
        else:
            price_str = f"{off['price']:.2f}{CURRENCY}"
        stock_str = "❌" if off["stock"] <= 0 else f"📦{off['stock']}"
        label = f"{off['name']} • {price_str} • {stock_str}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"off:{off['id']}")])
    buttons.append([InlineKeyboardButton(t(lang, "btn_back_services"), callback_data="catalog")])
    return InlineKeyboardMarkup(buttons)


def offer_detail_keyboard(lang, offer):
    buttons = []
    if offer["price"] is not None and offer["stock"] > 0:
        buttons.append([InlineKeyboardButton(t(lang, "btn_buy"),
                                             callback_data=f"buy:{offer['id']}")])
    buttons.append([InlineKeyboardButton(t(lang, "btn_back"),
                                         callback_data=f"svc:{offer['service_id']}")])
    return InlineKeyboardMarkup(buttons)


def paid_keyboard(lang, order_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_paid"), callback_data=f"paid:{order_id}")],
    ])


def affiliate_keyboard(lang, referral_link, share_text):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "affiliate_share"),
                              switch_inline_query=share_text)],
        [InlineKeyboardButton(t(lang, "affiliate_open"), url=referral_link)],
    ])
