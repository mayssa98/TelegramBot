"""Constructeurs de claviers inline et reply."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

import database as db
from config import ADMIN_ID, CURRENCY
from i18n import t


def lang_keyboard():
    active = set(db.shop_settings().get("active_languages", "fr,en,ar").split(","))
    choices = [
        ("fr", "🇫🇷 Français"),
        ("en", "🇬🇧 English"),
        ("ar", "🇸🇦 العربية"),
    ]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"lang:{code}")]
        for code, label in choices
        if code in active
    ])


def support_category_keyboard(lang):
    categories = ("payment", "delivery", "invalid_content", "order", "affiliation", "other")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, f"support_category_{category}"), callback_data=f"support_cat:{category}")]
        for category in categories
    ])


def support_order_keyboard(lang, orders):
    rows = [
        [InlineKeyboardButton(f"#{order['id']} — {order['offer_name']}", callback_data=f"support_order:{order['id']}")]
        for order in orders[:8]
    ]
    rows.append([InlineKeyboardButton(t(lang, "support_no_order"), callback_data="support_order:0")])
    return InlineKeyboardMarkup(rows)


def support_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "menu_support"), callback_data="support_cat:payment")],
        [InlineKeyboardButton(t(lang, "btn_main_menu"), callback_data="home")],
    ])


def main_menu_keyboard(lang, user_id):
    rows = [
        [t(lang, "menu_catalog")],
        [t(lang, "menu_account"), t(lang, "menu_orders")],
        [t(lang, "menu_support"), t(lang, "menu_help")],
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
        for _i, svc in enumerate(svcs):
            total = db.service_total_stock(svc["id"])
            stock_badge = "🟢" if total > 0 else "🔴"
            label = f"{stock_badge} {svc['emoji']} {svc['name']}"
            row.append(InlineKeyboardButton(label, callback_data=f"svc:{svc['id']}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

    buttons.append([InlineKeyboardButton(t(lang, "btn_refresh"), callback_data="catalog")])
    buttons.append([InlineKeyboardButton(t(lang, "btn_main_menu"), callback_data="home")])
    return InlineKeyboardMarkup(buttons)


def offers_keyboard(lang, service_id):
    buttons = []
    for off in db.list_offers(service_id):
        price_str = t(lang, "price_tbd") if off["price"] is None else f"{off['price']:.2f} {CURRENCY}"
        stock_str = "🔴 Épuisé" if off["stock"] <= 0 else f"🟢 Stock {off['stock']}"
        label = f"{off['name']} • {price_str} • {stock_str}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"off:{off['id']}")])
    buttons.append([InlineKeyboardButton(t(lang, "btn_back_services"), callback_data="catalog")])
    buttons.append([InlineKeyboardButton(t(lang, "btn_refresh"), callback_data=f"svc:{service_id}")])
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
        [InlineKeyboardButton(t(lang, "btn_copy_binance_id"), callback_data=f"copy_binance_id:{order_id}")],
        [InlineKeyboardButton(t(lang, "btn_copy_amount"), callback_data=f"copy_amount:{order_id}")],
        [InlineKeyboardButton(t(lang, "btn_paid"), callback_data=f"paid:{order_id}")],
        [InlineKeyboardButton(t(lang, "btn_cancel"), callback_data=f"cancel_buy:{order_id}")],
        [InlineKeyboardButton(t(lang, "btn_main_menu"), callback_data="home")],
    ])


def confirm_buy_keyboard(lang, offer_id):
    """Clavier de confirmation avant achat."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_confirm"), callback_data=f"confirm_buy:{offer_id}")],
        [InlineKeyboardButton(t(lang, "btn_cancel"), callback_data=f"cancel_buy:{offer_id}")],
    ])


def duplicate_order_keyboard(lang, existing_order_id, offer_id):
    """Clavier lorsqu'une commande identique existe déjà."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_continue_payment"), callback_data=f"continue_pay:{existing_order_id}")],
        [InlineKeyboardButton(t(lang, "btn_new_order"), callback_data=f"confirm_buy:{offer_id}")],
        [InlineKeyboardButton(t(lang, "btn_cancel"), callback_data=f"cancel_buy:{offer_id}")],
    ])


def post_delivery_keyboard(lang, order_id):
    """Clavier après livraison : confirmer ou signaler un problème."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_delivery_ok"), callback_data=f"delivery_ok:{order_id}")],
        [InlineKeyboardButton(t(lang, "btn_delivery_problem"), callback_data=f"delivery_problem:{order_id}")],
    ])


def affiliate_keyboard(lang, referral_link, share_text):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "affiliate_share"),
                              switch_inline_query=share_text)],
        [InlineKeyboardButton(t(lang, "affiliate_open"), url=referral_link)],
    ])

