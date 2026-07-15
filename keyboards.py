"""Constructeurs de claviers inline et reply."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

import database as db
from config import ADMIN_ID
from i18n import t


def compact_offer_name(name, max_len=34):
    clean_name = " ".join(str(name or "").split())
    if len(clean_name) <= max_len:
        return clean_name
    return clean_name[: max_len - 3].rstrip() + "..."


def offer_button_label(lang, offer):
    price_str = t(lang, "price_tbd") if offer["price"] is None else f"${offer['price']:.2f}"
    stock = int(offer.get("stock") or 0)
    if stock >= 10:
        stock_status = "\U0001f7e9"
    elif stock > 0:
        stock_status = "\U0001f7e8"
    else:
        stock_status = "\U0001f7e5"
    stock_str = f"\U0001f4e6 {stock}" if stock > 0 else "\U0001f534 0 manual"
    warranty = (offer.get("note") or "").strip()
    if not warranty:
        warranty = "Full Warranty"
    return f"{stock_status} {compact_offer_name(offer['name'])} | {warranty} | {price_str} | {stock_str}"


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
    rows = [
        [InlineKeyboardButton(t(lang, f"support_category_{category}"), callback_data=f"support_cat:{category}")]
        for category in categories
    ]
    rows.append([InlineKeyboardButton(t(lang, "btn_main_menu"), callback_data="home")])
    return InlineKeyboardMarkup(rows)


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
        [t(lang, "menu_catalog"), t(lang, "menu_orders")],
        [t(lang, "menu_account"), t(lang, "menu_affiliate")],
        [t(lang, "menu_support"), t(lang, "menu_help")],
        [t(lang, "menu_lang")],
    ]
    if user_id == ADMIN_ID:
        rows.append([t(lang, "menu_admin")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def home_keyboard(lang, user_id):
    rows = [
        [InlineKeyboardButton(t(lang, "menu_catalog"), callback_data="catalog")],
        [
            InlineKeyboardButton(t(lang, "menu_orders"), callback_data="orders"),
            InlineKeyboardButton(t(lang, "menu_account"), callback_data="account"),
        ],
        [
            InlineKeyboardButton(t(lang, "menu_affiliate"), callback_data="affiliate"),
            InlineKeyboardButton(t(lang, "menu_support"), callback_data="support"),
        ],
        [
            InlineKeyboardButton(t(lang, "menu_help"), callback_data="help"),
            InlineKeyboardButton(t(lang, "menu_lang"), callback_data="language"),
        ],
    ]
    if user_id == ADMIN_ID:
        rows.append([InlineKeyboardButton(t(lang, "menu_admin"), callback_data="adm_panel")])
    return InlineKeyboardMarkup(rows)


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

    for _cat, svcs in categories.items():
        row = []
        for _i, svc in enumerate(svcs):
            total = db.service_total_stock(svc["id"])
            stock_badge = "🟢" if total > 0 else "🔴"
            label = f"{stock_badge} {svc['emoji']} {compact_offer_name(svc['name'], 22)}"
            row.append(InlineKeyboardButton(label, callback_data=f"svc:{svc['id']}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

    buttons.append([
        InlineKeyboardButton(t(lang, "btn_refresh_short"), callback_data="catalog"),
        InlineKeyboardButton(t(lang, "btn_main_menu_short"), callback_data="home"),
    ])
    return InlineKeyboardMarkup(buttons)


def onboarding_keyboard(lang, step):
    if step < 3:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(t(lang, "onboarding_next"), callback_data=f"tour:{step + 1}"),
        ]])
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "onboarding_start"), callback_data="catalog"),
    ]])


def offers_keyboard(lang, service_id):
    buttons = []
    for off in db.list_offers(service_id):
        buttons.append([InlineKeyboardButton(offer_button_label(lang, off), callback_data=f"off:{off['id']}")])
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


def quantity_keyboard(lang, offer, page=0, page_size=20):
    stock = max(1, int(offer.get("stock", 1)))
    total_pages = max(1, (stock + page_size - 1) // page_size)
    page = max(0, min(int(page), total_pages - 1))
    start = page * page_size + 1
    end = min(stock, start + page_size - 1)
    rows = []
    row = []
    for qty in range(start, end + 1):
        row.append(InlineKeyboardButton(str(qty), callback_data=f"buyq:{offer['id']}:{qty}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"qty_page:{offer['id']}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"qty_page:{offer['id']}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(t(lang, "btn_back"), callback_data=f"off:{offer['id']}")])
    return InlineKeyboardMarkup(rows)


def paid_keyboard(lang, order_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "btn_copy_binance_id"), callback_data=f"copy_binance_id:{order_id}"),
            InlineKeyboardButton(t(lang, "btn_copy_amount"), callback_data=f"copy_amount:{order_id}"),
        ],
        [InlineKeyboardButton(t(lang, "btn_paid"), callback_data=f"paid:{order_id}")],
        [
            InlineKeyboardButton(t(lang, "btn_cancel_short"), callback_data=f"cancel_buy:{order_id}"),
            InlineKeyboardButton(t(lang, "btn_main_menu_short"), callback_data="home"),
        ],
    ])


def orders_keyboard(lang, orders=None):
    rows = []
    for order in (orders or [])[:5]:
        rows.append([InlineKeyboardButton(
            f"🧾 #{order['id']} · {compact_offer_name(order['offer_name'], 24)}",
            callback_data=f"order_view:{order['id']}",
        )])
    rows.append([
        InlineKeyboardButton(t(lang, "menu_catalog"), callback_data="catalog"),
        InlineKeyboardButton(t(lang, "btn_main_menu_short"), callback_data="home"),
    ])
    return InlineKeyboardMarkup(rows)


def confirm_buy_keyboard(lang, offer_id, qty=1):
    """Clavier de confirmation avant achat."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_confirm"), callback_data=f"confirm_buy:{offer_id}:{qty}")],
        [InlineKeyboardButton(t(lang, "btn_cancel"), callback_data=f"cancel_buy:{offer_id}")],
    ])


def duplicate_order_keyboard(lang, existing_order_id, offer_id, qty=1):
    """Clavier lorsqu'une commande identique existe déjà."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_continue_payment"), callback_data=f"continue_pay:{existing_order_id}")],
        [InlineKeyboardButton(t(lang, "btn_new_order"), callback_data=f"confirm_buy:{offer_id}:{qty}")],
        [InlineKeyboardButton(t(lang, "btn_cancel"), callback_data=f"cancel_buy:{offer_id}")],
    ])


def post_delivery_keyboard(lang, order_id):
    """Clavier après livraison : confirmer ou signaler un problème."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_delivery_ok"), callback_data=f"delivery_ok:{order_id}")],
        [InlineKeyboardButton(t(lang, "btn_delivery_problem"), callback_data=f"delivery_problem:{order_id}")],
        [
            InlineKeyboardButton("⭐ Avis", callback_data=f"rate:{order_id}"),
            InlineKeyboardButton(t(lang, "menu_catalog"), callback_data="catalog"),
        ],
    ])


def rating_keyboard(order_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"{score}⭐", callback_data=f"rating:{order_id}:{score}")
        for score in range(1, 6)
    ]])


def affiliate_keyboard(lang, referral_link, share_text):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "affiliate_share"),
                              switch_inline_query=share_text)],
        [InlineKeyboardButton(t(lang, "affiliate_open"), url=referral_link)],
    ])

