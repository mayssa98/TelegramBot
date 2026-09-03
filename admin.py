"""Vues et actions du panneau administrateur."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import database as db
from app.domain import warranty_service
from config import ADMIN_ID, CURRENCY
from i18n import TRANSLATIONS


def _safe_custom_emoji_id(value):
    """Ignore regular Unicode emoji accidentally stored as Premium icon IDs."""
    normalized = str(value or "").strip()
    return normalized if normalized and normalized.isascii() else None


def _service_button_text(service):
    icon_id = _safe_custom_emoji_id(service.get("custom_emoji_id"))
    left = "" if icon_id else str(service.get("emoji") or "").strip()
    name = service.get("name") or f"Service #{service['id']}"
    right = str(service.get("suffix_emoji") or "").strip()
    return " ".join(part for part in (left, name, right) if part)[:64]


TEXT_CATEGORIES = [
    ("menus", "🏠 Menus et boutons"),
    ("payments", "💳 Paiements et Binance Pay"),
    ("catalog", "🛍 Catalogue et offres"),
    ("alerts", "✨ Alertes stocks et ventes flash"),
    ("channel", "📣 Telegram Channel"),
    ("orders", "📦 Commandes et livraison"),
    ("support", "🎫 Support et avis"),
    ("affiliate", "🎁 Affiliation et fidélité"),
    ("account", "👤 Compte et informations"),
    ("admin", "🛠 Administration"),
    ("other", "📝 Autres textes"),
]


def text_category_for_key(key):
    if key in {
        "channel_stock_announcement", "offer_stock_announcement",
        "flash_sale_announcement",
    }:
        return "alerts"
    rules = [
        ("admin", ("admin_",)),
        ("channel", ("channel_", "btn_channel_", "btn_join_channel", "btn_verify_join")),
        ("payments", ("payment_", "topup_", "wallet_", "ask_txid", "verifying", "copy_", "order_created", "btn_paid", "btn_pay_")),
        ("catalog", ("catalog_", "service_", "offer_", "stock_", "choose_quantity", "quantity_", "confirm_purchase", "price_", "out_of_stock", "cat_")),
        ("orders", ("orders_", "order_", "delivery_", "status_", "otp_", "duplicate_order", "already_paid", "cancelled_")),
        ("support", ("support_", "ticket_", "rating_")),
        ("affiliate", ("affiliate_", "loyalty_")),
        ("account", ("profile_", "terms_", "privacy_", "help_", "welcome", "onboarding_", "lang_", "channel_")),
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
    maintenance_enabled = db.shop_settings()["maintenance_enabled"]
    maintenance_label = (
        "🔴 Full maintenance lock: ON"
        if maintenance_enabled
        else "🟢 Full maintenance lock: OFF"
    )
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Commandes payées", callback_data="adm_list:paid")],
        [InlineKeyboardButton("📦 Catalogue", callback_data="adm_catalog")],
        [InlineKeyboardButton("💗 Lovable Extension", callback_data="adm_lovable")],
        [InlineKeyboardButton("📢 Créer une annonce", callback_data="adm_broadcast_message")],
        [InlineKeyboardButton("🧹 Annonces envoyées", callback_data="adm_broadcast_history")],
        [InlineKeyboardButton("🎫 Tickets support", callback_data="adm_tickets")],
        [InlineKeyboardButton("👥 Activité utilisateurs", callback_data="adm_user_activity")],
        [InlineKeyboardButton(maintenance_label, callback_data="adm_maintenance_toggle")],
        [InlineKeyboardButton("🎛 Personnaliser le bot", callback_data="adm_customize")],
    ])


def broadcast_kind_label(kind):
    return {
        "stock": "✨ Nouveau stock",
        "restock_digest": "✨ Stocks individuels (ancien)",
        "flash_sale": "🔥 Vente flash",
        "api_flash_sale": "🔥 Vente flash",
        "admin_message": "📢 Annonce libre",
        "maintenance": "🛠 Maintenance",
        "affiliate_update": "🎁 Mise à jour affiliation",
    }.get(str(kind), "📣 Annonce")


def broadcast_history_keyboard(history):
    rows = []
    for job in history:
        active = int(job.get("active_message_count") or 0)
        status = "🗑" if active == 0 else "🟢"
        rows.append([InlineKeyboardButton(
            f"{status} {broadcast_kind_label(job.get('kind'))} · {active}/{int(job.get('tracked_count') or 0)}",
            callback_data=f"adm_broadcast_view:{job['id']}",
        )])
    if not rows:
        rows.append([InlineKeyboardButton("Aucune annonce suivie", callback_data="adm_text_noop")])
    rows.extend([
        [InlineKeyboardButton("🔄 Actualiser", callback_data="adm_broadcast_history")],
        [InlineKeyboardButton("⬅️ Administration", callback_data="adm_panel")],
    ])
    return InlineKeyboardMarkup(rows)


def broadcast_delete_keyboard(job):
    job_id = int(job["id"])
    rows = []
    if int(job.get("active_message_count") or 0) > 0:
        rows.append([InlineKeyboardButton(
            "🗑 Supprimer chez tous les clients",
            callback_data=f"adm_broadcast_confirm:{job_id}",
            style="danger",
        )])
    rows.append([InlineKeyboardButton("⬅️ Historique", callback_data="adm_broadcast_history")])
    return InlineKeyboardMarkup(rows)


def broadcast_delete_confirmation_keyboard(job_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ Confirmer la suppression partout",
            callback_data=f"adm_broadcast_delete:{int(job_id)}",
            style="danger",
        )],
        [InlineKeyboardButton("❌ Annuler", callback_data=f"adm_broadcast_view:{int(job_id)}")],
    ])


def user_activity_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Actualiser", callback_data="adm_user_activity")],
        [InlineKeyboardButton("⬅️ Retour", callback_data="adm_panel")],
    ])


def customize_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Alertes stocks & flash", callback_data="adm_alert_design")],
        [InlineKeyboardButton("✏️ Textes du bot", callback_data="adm_texts")],
        [InlineKeyboardButton("🔘 Boutons du bot", callback_data="adm_buttons")],
        [InlineKeyboardButton("🎨 Design des tickets", callback_data="adm_ticket_style")],
        [InlineKeyboardButton("⬅️ Retour", callback_data="adm_panel")],
    ])


def alert_design_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Nouveau stock (un produit)", callback_data="adm_text_key:channel_stock_announcement")],
        [InlineKeyboardButton("✨ Offre remise en avant", callback_data="adm_text_key:offer_stock_announcement")],
        [InlineKeyboardButton("🔥 Vente flash", callback_data="adm_text_key:flash_sale_announcement")],
        [InlineKeyboardButton("⬅️ Personnalisation", callback_data="adm_customize")],
    ])


def ticket_style_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Modifier le titre", callback_data="adm_ticket_style_edit:title")],
        [InlineKeyboardButton("↩️ Modifier l’instruction de réponse", callback_data="adm_ticket_style_edit:reply_hint")],
        [InlineKeyboardButton("🏷️ Modifier la signature", callback_data="adm_ticket_style_edit:footer")],
        [InlineKeyboardButton("👁 Aperçu", callback_data="adm_ticket_style_preview")],
        [InlineKeyboardButton("♻️ Restaurer le design", callback_data="adm_ticket_style_reset")],
        [InlineKeyboardButton("⬅️ Personnalisation", callback_data="adm_customize")],
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
        ("catalog", "Catalogue"), ("lovable", "Lovable Unlimited"),
        ("topup", "Recharge"), ("orders", "Commandes"),
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
    rows = [[InlineKeyboardButton("🎨 Design des tickets", callback_data="adm_ticket_style")]]
    rows.extend([[InlineKeyboardButton(f"#{x['id']} • utilisateur {x['user_id']}", callback_data=f"adm_ticket:{x['id']}")] for x in tickets])
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
    preorder = "\n⏳ *Pre-order (+10%)*" if o.get("is_preorder") else ""
    warranty = warranty_service.order_warranty_label(o) or "—"
    return (f"🧾 *Commande #{o['id']}*{preorder}\nUtilisateur: `{o['user_id']}`\n"
            f"Produit: {o['service_name']} — {o['offer_name']}\n"
            f"Quantité: {o['qty']}\nTotal: *{o['total_price']:.2f} {CURRENCY}*\n"
            f"Garantie: {warranty}\n"
            f"Statut: `{o['status']}`\nTXID: `{o['txid'] or '—'}`")


def order_detail_keyboard(o):
    rows = []
    if o and o["status"] in {"paid", "payment_confirmed"}:
        if db.is_otp_service_name(o.get("service_name")):
            workflow = str(o.get("otp_workflow_status") or "")
            if workflow == "customer_agreed":
                rows.extend(codex_otp_request_keyboard(o["id"]).inline_keyboard)
            elif workflow != "number_sent":
                rows.extend(codex_number_request_keyboard(o["id"]).inline_keyboard)
        else:
            rows.extend(manual_delivery_request_keyboard(o["id"]).inline_keyboard)
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="adm_panel")])
    return InlineKeyboardMarkup(rows)


def manual_delivery_request_keyboard(order_id):
    """Let the administrator message the customer or complete the delivery."""
    order_id = int(order_id)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "💬 Envoyer un message",
            callback_data=f"adm_client_message:{order_id}",
        ),
        InlineKeyboardButton(
            "🎁 Envoyer la commande",
            callback_data=f"adm_deliver:{order_id}",
            style="success",
        ),
    ]])


def codex_number_request_keyboard(order_id):
    """Start the first stage of a paid Codex-number order."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "📱 Send number",
            callback_data=f"adm_codex_number:{int(order_id)}",
            style="success",
        ),
    ]])


def codex_otp_request_keyboard(order_id):
    """Allow OTP entry only after the customer accepted the number."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🔐 Send OTP code",
            callback_data=f"adm_codex_otp:{int(order_id)}",
            style="success",
        ),
    ]])


def onchain_payment_review_keyboard(order_id):
    """Accept or reject one pending BSC/Polygon payment."""
    order_id = int(order_id)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ Accepter",
            callback_data=f"adm_onchain_approve:{order_id}",
            style="success",
        ),
        InlineKeyboardButton(
            "❌ Refuser",
            callback_data=f"adm_onchain_reject:{order_id}",
            style="danger",
        ),
    ]])


def catalog_admin_keyboard():
    rows = [[InlineKeyboardButton(
        _service_button_text(s),
        callback_data=f"adm_svc:{s['id']}",
        icon_custom_emoji_id=_safe_custom_emoji_id(s.get("custom_emoji_id")),
        style=None if db.is_official_subscriptions_service(s) else (
            "success" if s["active"] else "danger"
        ),
    )] for s in db.list_services(active_only=False)]
    rows.append([InlineKeyboardButton("➕ Ajouter un service", callback_data="adm_addsvc")])
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="adm_panel")])
    return InlineKeyboardMarkup(rows)


def service_admin_keyboard(service_id):
    svc = db.get_service(service_id)
    rows = [[InlineKeyboardButton(
        o.get("name") or f"Offre #{o['id']}",
        callback_data=f"adm_off:{o['id']}",
        icon_custom_emoji_id=_safe_custom_emoji_id(o.get("custom_emoji_id")),
        style="success" if o["active"] else "danger",
    )] for o in db.list_offers(service_id, active_only=False)]
    rows.extend([
        [InlineKeyboardButton("➕ Ajouter une offre", callback_data=f"adm_addoff:{service_id}")],
        [InlineKeyboardButton("✏️ Nom", callback_data=f"adm_svcname:{service_id}")],
        [InlineKeyboardButton("⬅️ Emoji gauche", callback_data=f"adm_svcemoji:{service_id}"),
         InlineKeyboardButton("Emoji droit ➡️", callback_data=f"adm_svcsuffix:{service_id}")],
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
        [InlineKeyboardButton(
            "⏹ Arrêter la vente flash" if off.get("flash_sale_active")
            else "⚡ Lancer une vente flash",
            callback_data=(
                f"adm_flash_stop:{offer_id}"
                if off.get("flash_sale_active")
                else f"adm_flash_start:{offer_id}"
            ),
        )],
        [InlineKeyboardButton(
            "📣 Envoyer une annonce (prix + stock)",
            callback_data=f"adm_broadcast_offer:{offer_id}",
        )],
        [InlineKeyboardButton(
            "♾ Désactiver le stock illimité" if off.get("unlimited_stock")
            else "♾ Activer le stock illimité",
            callback_data=f"adm_unlimited:{offer_id}",
        )],
        [InlineKeyboardButton("✏️ Modifier le nom", callback_data=f"adm_offname:{offer_id}")],
        [InlineKeyboardButton("📂 Déplacer vers un autre service", callback_data=f"adm_offmove:{offer_id}")],
        [InlineKeyboardButton("🎨 Emoji animé", callback_data=f"adm_offemoji:{offer_id}")],
        [InlineKeyboardButton("📄 Description", callback_data=f"adm_offdesc:{offer_id}")],
        [InlineKeyboardButton("🛡 Garantie", callback_data=f"adm_offnote:{offer_id}")],
        [InlineKeyboardButton("📅 Période (jours)", callback_data=f"adm_offperiod:{offer_id}")],
        [InlineKeyboardButton("⏸ Désactiver" if off["active"] else "▶️ Activer",
                              callback_data=f"adm_offtoggle:{offer_id}"),
         InlineKeyboardButton("🗑 Archiver", callback_data=f"adm_offdel:{offer_id}")],
        [InlineKeyboardButton("⬅️ Retour", callback_data=f"adm_svc:{off['service_id']}")],
    ])


def move_offer_keyboard(offer_id):
    offer = db.get_offer(int(offer_id))
    current_service_id = int((offer or {}).get("service_id") or 0)
    rows = []
    for service in db.list_services():
        if int(service["id"]) == current_service_id or db.is_otp_service_name(service.get("name")):
            continue
        service_name = service.get("name") or f"Service #{service['id']}"
        rows.append([InlineKeyboardButton(
            f"{service.get('emoji') or '📦'} {service_name}",
            callback_data=f"adm_offmove_to:{offer_id}:{service['id']}",
        )])
    rows.append([InlineKeyboardButton("⬅️ Annuler", callback_data=f"adm_off:{offer_id}")])
    return InlineKeyboardMarkup(rows)


async def post_purchase_to_channel(context, order):
    """Compatibility no-op: purchases must remain private to the customer/admin."""
    return False


async def notify_new_order(context, order):
    await context.bot.send_message(
        ADMIN_ID, order_detail_text(order), parse_mode="Markdown",
        reply_markup=order_detail_keyboard(order),
    )


async def notify_manual_delivery_request(context, order):
    """Request the manual delivery in the private administrator bot chat."""
    await context.bot.send_message(
        ADMIN_ID,
        "📦 *Livraison manuelle demandée*\n\n"
        f"{order_detail_text(order)}\n\n"
        "Choisissez *Envoyer un message* pour informer le client sans terminer "
        "la commande, ou *Envoyer la commande* pour transmettre le compte/code "
        "et confirmer la livraison.",
        parse_mode="Markdown",
        reply_markup=manual_delivery_request_keyboard(order["id"]),
    )
