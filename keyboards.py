"""Constructeurs de claviers inline et reply."""
import html
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

import database as db
from config import ADMIN_ID, REQUIRED_CHANNEL
from i18n import t


BUTTON_TEXT_KEYS = {
    "menu_catalog", "menu_orders", "menu_topup", "menu_account", "menu_affiliate",
    "menu_support", "menu_lang", "menu_admin", "btn_main_menu", "support_no_order",
    "catalog_request_button",
    "topup_claim", "btn_main_menu_short", "btn_refresh_short", "onboarding_next",
    "onboarding_start", "btn_back_services", "btn_buy", "btn_back", "btn_paid",
    "btn_cancel_short", "btn_verify_txid", "btn_cancel_order", "btn_pay_wallet",
    "btn_pay_binance", "btn_cancel", "btn_continue_payment", "btn_new_order",
    "affiliate_copy", "affiliate_share", "orders_all", "btn_join_channel", "btn_verify_join", "btn_channel_buy_now",
}


def is_button_text_key(key):
    return key in BUTTON_TEXT_KEYS or str(key).startswith("support_category_")


def clean_translated_button_text(value):
    """Remove stored rich-text markup; Premium emoji is rendered by the icon field."""
    value = str(value or "").removeprefix("[[HTML]]")
    value = re.sub(r"<tg-emoji\b[^>]*>.*?</tg-emoji>", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"\[\[TGEMOJI:[^\]]+\]\]", "", value)
    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(html.unescape(value).split())[:64]


def translated_button(lang, key, *, callback_data=None, url=None, style=None, switch_inline_query=None):
    """Build an inline button with the admin-selected Premium emoji icon."""
    return InlineKeyboardButton(
        clean_translated_button_text(t(lang, key)),
        callback_data=callback_data, url=url, style=style,
        switch_inline_query=switch_inline_query,
        icon_custom_emoji_id=db.get_text_override_icon(key, lang) or None,
    )


def compact_offer_name(name, max_len=34):
    clean_name = " ".join(str(name or "").split())
    if len(clean_name) <= max_len:
        return clean_name
    return clean_name[: max_len - 3].rstrip() + "..."


def stock_badge(stock):
    """Return Telegram's closest visual equivalent to a colored button."""
    stock = int(stock or 0)
    if stock > 3:
        return "🟩"
    if stock > 0:
        return "🟦"
    return "🟥"


def stock_button_style(stock):
    """Map stock to Telegram's supported native button background styles."""
    stock = int(stock or 0)
    if stock > 3:
        return "success"
    if stock > 0:
        return "primary"
    if stock == 0:
        return "danger"
    return "danger"


def clean_button_name(value):
    """Remove decorative emoji characters from button text; icons use Telegram's icon field."""
    text = " ".join(str(value or "").split())
    return re.sub(r"^[^\w\d]+", "", text, flags=re.UNICODE).strip()


def offer_button_label(lang, offer):
    stock = int(offer.get("stock") or 0)
    stock_text = f"{t(lang, 'stock_label').title()}: {stock}"
    # Telegram limits button labels to 64 characters. Always reserve room for
    # the live stock quantity so a long offer name can never hide it.
    max_name_length = max(8, 64 - len(stock_text) - 3)
    name = compact_offer_name(clean_button_name(offer["name"]), max_name_length)
    return f"{name} | {stock_text}"


def lang_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
    ]])


def channel_offer_keyboard(lang, bot_username, offer_id):
    """Open a restocked offer privately from a public channel post."""
    deep_link = f"https://t.me/{str(bot_username).lstrip('@')}?start=offer_{int(offer_id)}"
    return InlineKeyboardMarkup([[
        translated_button(lang, "btn_channel_buy_now", url=deep_link, style="success"),
    ]])

def channel_join_keyboard(lang):
    """Require channel membership before unlocking the customer menu."""
    channel_url = f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"
    return InlineKeyboardMarkup([
        [translated_button(lang, "btn_join_channel", url=channel_url, style="primary")],
        [translated_button(lang, "btn_verify_join", callback_data="verify_channel_join", style="success")],
    ])

def support_category_keyboard(lang):
    categories = ("payment", "delivery", "invalid_content", "order", "affiliation", "other")
    rows = [
        [translated_button(lang, f"support_category_{category}", callback_data=f"support_cat:{category}")]
        for category in categories
    ]
    rows.append([translated_button(lang, "btn_main_menu", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def support_order_keyboard(lang, orders):
    rows = [
        [InlineKeyboardButton(f"#{order['id']} — {order['offer_name']}", callback_data=f"support_order:{order['id']}")]
        for order in orders[:8]
    ]
    rows.append([translated_button(lang, "support_no_order", callback_data="support_order:0")])
    return InlineKeyboardMarkup(rows)


def support_keyboard(lang):
    return InlineKeyboardMarkup([
        [translated_button(lang, "menu_support", callback_data="support_cat:payment")],
        [translated_button(lang, "btn_main_menu", callback_data="home")],
    ])


def main_menu_keyboard(lang, user_id):
    hidden = set(filter(None, (db.get_setting("hidden_home_actions", "") or "").split(",")))
    candidates = [
        [("catalog", t(lang, "menu_catalog")), ("orders", t(lang, "menu_orders"))],
        [("topup", t(lang, "menu_topup"))],
        [("account", t(lang, "menu_account")), ("affiliate", t(lang, "menu_affiliate"))],
        [("support", t(lang, "menu_support")), ("language", t(lang, "menu_lang"))],
    ]
    rows = [[label for action, label in row if action not in hidden] for row in candidates]
    rows = [row for row in rows if row]
    if user_id == ADMIN_ID:
        rows.append([t(lang, "menu_admin")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def home_keyboard(lang, user_id):
    hidden = set(filter(None, (db.get_setting("hidden_home_actions", "") or "").split(",")))
    candidate_rows = [
        [translated_button(lang, "menu_catalog", callback_data="catalog")],
        [translated_button(lang, "menu_topup", callback_data="topup", style="success")],
        [
            translated_button(lang, "menu_orders", callback_data="orders"),
            translated_button(lang, "menu_account", callback_data="account"),
        ],
        [
            translated_button(lang, "menu_affiliate", callback_data="affiliate"),
            translated_button(lang, "menu_support", callback_data="support"),
        ],
        [
            translated_button(lang, "menu_lang", callback_data="language"),
        ],
    ]
    rows = []
    for row in candidate_rows:
        visible = [button for button in row if button.callback_data not in hidden]
        if visible:
            rows.append(visible)
    for button in db.list_custom_buttons():
        label = button.get(f"label_{lang}") or button.get("label_fr") or "Lien"
        rows.append([InlineKeyboardButton(label[:64], url=button["url"])])
    if user_id == ADMIN_ID:
        rows.append([translated_button(lang, "menu_admin", callback_data="adm_panel")])
    return InlineKeyboardMarkup(rows)


def topup_keyboard(lang):
    return InlineKeyboardMarkup([
        [translated_button(lang, "topup_claim", callback_data="topup_claim", style="success")],
        [translated_button(lang, "btn_main_menu_short", callback_data="home")],
    ])


def topup_verifying_keyboard(lang):
    return InlineKeyboardMarkup([
        [translated_button(lang, "btn_verify_txid", callback_data="topup_txid")],
        [translated_button(lang, "btn_main_menu_short", callback_data="home")],
    ])

def services_keyboard(lang):
    buttons = []
    services = db.list_services_with_stock()

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
            total = svc.get("total_stock", 0)
            safe_name = clean_button_name(svc.get("name")) or f"Service #{svc['id']}"
            label = compact_offer_name(safe_name, 28)
            row.append(InlineKeyboardButton(
                label,
                callback_data=f"svc:{svc['id']}",
                style=stock_button_style(total),
                icon_custom_emoji_id=svc.get("custom_emoji_id") or None,
            ))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

    buttons.append([
        translated_button(lang, "catalog_request_button", callback_data="catalog_request"),
    ])
    buttons.append([
        translated_button(lang, "btn_refresh_short", callback_data="catalog"),
        translated_button(lang, "btn_main_menu_short", callback_data="home"),
    ])
    return InlineKeyboardMarkup(buttons)


def onboarding_keyboard(lang, step):
    if step < 3:
        return InlineKeyboardMarkup([[
            translated_button(lang, "onboarding_next", callback_data=f"tour:{step + 1}"),
        ]])
    return InlineKeyboardMarkup([[
        translated_button(lang, "onboarding_start", callback_data="catalog"),
    ]])


def offers_keyboard(lang, service_id):
    buttons = []
    for off in db.list_offers(service_id):
        safe_offer = dict(off)
        safe_offer["name"] = clean_button_name(off.get("name")) or f"Offre #{off['id']}"
        buttons.append([InlineKeyboardButton(
            offer_button_label(lang, safe_offer),
            callback_data=f"off:{off['id']}",
            style=stock_button_style(off.get("stock")),
            icon_custom_emoji_id=(
                db.get_text_override_icon("stock_label", lang)
                or off.get("custom_emoji_id")
                or None
            ),
        )])
    buttons.append([translated_button(lang, "btn_back_services", callback_data="catalog")])
    return InlineKeyboardMarkup(buttons)


def offer_detail_keyboard(lang, offer):
    buttons = []
    if offer["price"] is not None and offer["stock"] > 0:
        buttons.append([translated_button(lang, "btn_buy", callback_data=f"buy:{offer['id']}")])
    buttons.append([translated_button(lang, "btn_back", callback_data=f"svc:{offer['service_id']}")])
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
    rows.append([translated_button(lang, "btn_back", callback_data=f"off:{offer['id']}")])
    return InlineKeyboardMarkup(rows)


def paid_keyboard(lang, order_id, binance_id="", total="", currency="USDT"):
    return InlineKeyboardMarkup([
        [translated_button(lang, "btn_paid", callback_data=f"verify_auto:{order_id}")],
        [
            translated_button(lang, "btn_cancel_short", callback_data=f"cancel_buy:{order_id}"),
            translated_button(lang, "btn_main_menu_short", callback_data="home"),
        ],
    ])


def txid_verify_keyboard(lang, order_id):
    return InlineKeyboardMarkup([
        [translated_button(lang, "btn_verify_txid", callback_data=f"paid:{order_id}")],
        [translated_button(lang, "btn_cancel_order", callback_data=f"cancel_buy:{order_id}")],
        [translated_button(lang, "btn_main_menu_short", callback_data="home")],
    ])


def orders_services_keyboard(lang, groups, total):
    rows = [
        [InlineKeyboardButton(
            f"{group['emoji']} {compact_offer_name(group['name'], 28)} ({group['count']})",
            callback_data=f"orders_group:{index}",
            style="primary",
        )]
        for index, group in enumerate(groups)
    ]
    rows.append([InlineKeyboardButton(
        t(lang, "orders_all", count=total),
        callback_data="orders_export:all",
        style="success",
        icon_custom_emoji_id=db.get_text_override_icon("orders_all", lang) or None,
    )])
    rows.append([translated_button(lang, "btn_back", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def orders_keyboard(lang, orders=None):
    """Small generic navigation keyboard kept for help and order detail views."""
    return InlineKeyboardMarkup([[
        translated_button(lang, "menu_orders", callback_data="orders"),
        translated_button(lang, "btn_main_menu_short", callback_data="home"),
    ]])


def confirm_buy_keyboard(lang, offer_id, qty=1):
    """Clavier de confirmation avant achat."""
    return InlineKeyboardMarkup([
        [translated_button(lang, "btn_pay_wallet", callback_data=f"pay_wallet:{offer_id}:{qty}")],
        [translated_button(lang, "btn_pay_binance", callback_data=f"pay_binance:{offer_id}:{qty}")],
        [translated_button(lang, "btn_cancel", callback_data=f"cancel_buy:{offer_id}")],
    ])


def duplicate_order_keyboard(lang, existing_order_id, offer_id, qty=1):
    """Clavier lorsqu'une commande identique existe déjà."""
    return InlineKeyboardMarkup([
        [translated_button(lang, "btn_continue_payment", callback_data=f"continue_pay:{existing_order_id}")],
        [translated_button(lang, "btn_new_order", callback_data=f"confirm_buy:{offer_id}:{qty}")],
        [translated_button(lang, "btn_cancel", callback_data=f"cancel_buy:{offer_id}")],
    ])


def post_delivery_keyboard(lang, order_id):
    """Clavier minimal affiché après la livraison."""
    return InlineKeyboardMarkup([[
        translated_button(lang, "menu_catalog", callback_data="catalog"),
    ]])


def rating_keyboard(order_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"{score}⭐", callback_data=f"rating:{order_id}:{score}")
        for score in range(1, 6)
    ]])


def affiliate_keyboard(lang, referral_link, share_text):
    return InlineKeyboardMarkup([
        [translated_button(lang, "affiliate_copy", callback_data="affiliate_copy")],
        [translated_button(lang, "affiliate_share", switch_inline_query=share_text)],
        [translated_button(lang, "btn_main_menu_short", callback_data="home")],
    ])

