"""Vues et actions du panneau administrateur."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import database as db
from config import ADMIN_ID, CURRENCY
from i18n import TRANSLATIONS


TEXT_CATEGORIES = [
    ("menus", "🏠 Menus et boutons"),
    ("payments", "💳 Paiements et Binance Pay"),
    ("catalog", "🛍 Catalogue et offres"),
    ("orders", "📦 Commandes et livraison"),
    ("support", "🎫 Support et avis"),
    ("affiliate", "🎁 Affiliation et fidélité"),
    ("account", "👤 Compte et informations"),
    ("admin", "🛠 Administration"),
    ("other", "📝 Autres textes"),
]


def text_category_for_key(key):
    rules = [
        ("admin", ("admin_",)),
        ("payments", ("payment_", "topup_", "wallet_", "ask_txid", "verifying", "copy_", "order_created", "btn_paid", "btn_pay_")),
        ("catalog", ("catalog_", "service_", "offer_", "stock_", "choose_quantity", "quantity_", "confirm_purchase", "price_", "out_of_stock", "cat_")),
        ("orders", ("orders_", "order_", "delivery_", "status_", "duplicate_order", "already_paid", "cancelled_")),
        ("support", ("support_", "ticket_", "rating_")),
        ("affiliate", ("affiliate_", "loyalty_")),
        ("account", ("profile_", "terms_", "privacy_", "help_", "welcome", "onboarding_", "lang_")),
        ("menus", ("menu_", "btn_")),
    ]
    for category, prefixes in rules:
        if key.startswith(prefixes) or key in prefixes:
            return category
    return "other"


def text_categories_keyboard():
    counts = {slug: 0 for slug, _label in TEXT_CATEGORIES}
    for key in TRANSLATIONS:
        counts[text_category_for_key(key)] += 1
    rows = [[InlineKeyboardButton(
        f"{label} ({counts[slug]})", callback_data=f"adm_text_cat:{slug}:0"
    )] for slug, label in TEXT_CATEGORIES if counts[slug]]
    rows.append([InlineKeyboardButton("⬅️ Personnalisation", callback_data="adm_customize")])
    return InlineKeyboardMarkup(rows)


def texts_category_keyboard(category, page=0, page_size=8):
    keys = sorted(key for key in TRANSLATIONS if text_category_for_key(key) == category)
    total_pages = max(1, (len(keys) + page_size - 1) // page_size)
    page = max(0, min(int(page), total_pages - 1))
    visible = keys[page * page_size:(page + 1) * page_size]
    rows = [[InlineKeyboardButton(f"✏️ {key}", callback_data=f"adm_text_key:{key}")] for key in visible]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_text_cat:{category}:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="adm_text_noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_text_cat:{category}:{page + 1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton("🗂 Catégories", callback_data="adm_texts")])
    return InlineKeyboardMarkup(rows)


def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Commandes payées", callback_data="adm_list:paid")],
        [InlineKeyboardButton("📦 Catalogue", callback_data="adm_catalog")],
        [InlineKeyboardButton("🎫 Tickets support", callback_data="adm_tickets")],
        [InlineKeyboardButton("🎛 Personnaliser le bot", callback_data="adm_customize")],
    ])


def customize_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Textes du bot", callback_data="adm_texts")],
        [InlineKeyboardButton("🔘 Boutons du bot", callback_data="adm_buttons")],
        [InlineKeyboardButton("⬅️ Retour", callback_data="adm_panel")],
    ])


def texts_editor_keyboard(page=0, page_size=8):
    keys = sorted(TRANSLATIONS)
    total_pages = max(1, (len(keys) + page_size - 1) // page_size)
    page = max(0, min(int(page), total_pages - 1))
    visible = keys[page * page_size:(page + 1) * page_size]
    rows = [[InlineKeyboardButton(f"✏️ {key}", callback_data=f"adm_text_key:{key}")] for key in visible]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_text_page:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="adm_text_noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_text_page:{page + 1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton("⬅️ Personnalisation", callback_data="adm_customize")])
    return InlineKeyboardMarkup(rows)


def text_languages_keyboard(key):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data=f"adm_text_lang:{key}:en")],
        [InlineKeyboardButton("⬅️ Catégories", callback_data="adm_texts")],
    ])


def text_navigator_keyboard(index):
    keys = sorted(TRANSLATIONS)
    index = max(0, min(int(index), len(keys) - 1))
    key = keys[index]
    rows = [
        [InlineKeyboardButton("🇬🇧 English", callback_data=f"adm_text_lang:{key}:en")],
    ]
    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_text_view:{index - 1}"))
    nav.append(InlineKeyboardButton(f"{index + 1}/{len(keys)}", callback_data="adm_text_noop"))
    if index < len(keys) - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_text_view:{index + 1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton("⬅️ Personnalisation", callback_data="adm_customize")])
    return InlineKeyboardMarkup(rows)


def buttons_editor_keyboard():
    hidden = set(filter(None, (db.get_setting("hidden_home_actions", "") or "").split(",")))
    standard = [
        ("catalog", "Catalogue"), ("topup", "Recharge"), ("orders", "Commandes"),
        ("account", "Compte"), ("affiliate", "Affiliation"),
        ("support", "Support"), ("language", "Langue"),
    ]
    rows = [[InlineKeyboardButton(
        f"{'❌ Masqué' if action in hidden else '✅ Visible'} — {label}",
        callback_data=f"adm_btn_toggle:{action}",
    )] for action, label in standard]
    rows.append([InlineKeyboardButton("➕ Ajouter un bouton URL", callback_data="adm_btn_add")])
    for button in db.list_custom_buttons(active_only=False):
        rows.append([InlineKeyboardButton(
            f"🗑 {button.get('label_fr') or 'Bouton'}",
            callback_data=f"adm_btn_del:{button['id']}",
        )])
    rows.append([InlineKeyboardButton("⬅️ Personnalisation", callback_data="adm_customize")])
    return InlineKeyboardMarkup(rows)


def tickets_keyboard():
    tickets = db.list_tickets(limit=50)
    rows = [[InlineKeyboardButton(f"#{x['id']} • utilisateur {x['user_id']}", callback_data=f"adm_ticket:{x['id']}")] for x in tickets]
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="adm_panel")])
    return InlineKeyboardMarkup(rows), tickets


def orders_list_keyboard(status):
    orders = db.list_orders(status=status, limit=50)
    rows = [[InlineKeyboardButton(
        f"#{o['id']} • {o['offer_name']} • {o['total_price']:.2f} {CURRENCY}",
        callback_data=f"adm_order:{o['id']}",
    )] for o in orders]
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="adm_panel")])
    return InlineKeyboardMarkup(rows), orders


def order_detail_text(o):
    if not o:
        return "Commande introuvable."
    return (f"🧾 *Commande #{o['id']}*\nUtilisateur: `{o['user_id']}`\n"
            f"Produit: {o['service_name']} — {o['offer_name']}\n"
            f"Quantité: {o['qty']}\nTotal: *{o['total_price']:.2f} {CURRENCY}*\n"
            f"Statut: `{o['status']}`\nTXID: `{o['txid'] or '—'}`")


def order_detail_keyboard(o):
    rows = []
    if o and o["status"] == "paid":
        rows.append([InlineKeyboardButton("🎁 Livrer", callback_data=f"adm_deliver:{o['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="adm_panel")])
    return InlineKeyboardMarkup(rows)


def catalog_admin_keyboard():
    rows = [[InlineKeyboardButton(
        s.get("name") or f"Service #{s['id']}",
        callback_data=f"adm_svc:{s['id']}",
        icon_custom_emoji_id=s.get("custom_emoji_id") or None,
        style="success" if s["active"] else "danger",
    )] for s in db.list_services(active_only=False)]
    rows.append([InlineKeyboardButton("➕ Ajouter un service", callback_data="adm_addsvc")])
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="adm_panel")])
    return InlineKeyboardMarkup(rows)


def service_admin_keyboard(service_id):
    svc = db.get_service(service_id)
    rows = [[InlineKeyboardButton(
        o.get("name") or f"Offre #{o['id']}",
        callback_data=f"adm_off:{o['id']}",
        icon_custom_emoji_id=o.get("custom_emoji_id") or None,
        style="success" if o["active"] else "danger",
    )] for o in db.list_offers(service_id, active_only=False)]
    rows.extend([
        [InlineKeyboardButton("➕ Ajouter une offre", callback_data=f"adm_addoff:{service_id}")],
        [InlineKeyboardButton("✏️ Nom", callback_data=f"adm_svcname:{service_id}"),
         InlineKeyboardButton("🎨 Emoji", callback_data=f"adm_svcemoji:{service_id}")],
        [InlineKeyboardButton("⏸ Désactiver" if svc["active"] else "▶️ Activer",
                              callback_data=f"adm_svctoggle:{service_id}"),
         InlineKeyboardButton("🗑 Archiver", callback_data=f"adm_svcdel:{service_id}")],
    ])
    rows.append([InlineKeyboardButton("⬅️ Catalogue", callback_data="adm_catalog")])
    return InlineKeyboardMarkup(rows)


def offer_admin_keyboard(offer_id):
    off = db.get_offer(offer_id)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Ajouter plusieurs comptes", callback_data=f"adm_inventory:{offer_id}")],
        [InlineKeyboardButton("🖼 Modifier l’image", callback_data=f"adm_offimage:{offer_id}")],
        [InlineKeyboardButton("💵 Modifier le prix", callback_data=f"adm_setprice:{offer_id}")],
        [InlineKeyboardButton("✏️ Modifier le nom", callback_data=f"adm_offname:{offer_id}")],
        [InlineKeyboardButton("🎨 Emoji animé", callback_data=f"adm_offemoji:{offer_id}")],
        [InlineKeyboardButton("📄 Description", callback_data=f"adm_offdesc:{offer_id}")],
        [InlineKeyboardButton("⏸ Désactiver" if off["active"] else "▶️ Activer",
                              callback_data=f"adm_offtoggle:{offer_id}"),
         InlineKeyboardButton("🗑 Archiver", callback_data=f"adm_offdel:{offer_id}")],
        [InlineKeyboardButton("⬅️ Retour", callback_data=f"adm_svc:{off['service_id']}")],
    ])


async def notify_new_order(context, order):
    await context.bot.send_message(
        ADMIN_ID, order_detail_text(order), parse_mode="Markdown",
        reply_markup=order_detail_keyboard(order),
    )
