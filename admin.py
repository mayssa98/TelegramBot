"""Vues et actions du panneau administrateur."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import database as db
from config import ADMIN_ID, CURRENCY


def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Commandes payées", callback_data="adm_list:paid")],
        [InlineKeyboardButton("📦 Catalogue", callback_data="adm_catalog")],
        [InlineKeyboardButton("🎫 Tickets support", callback_data="adm_tickets")],
    ])


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
        f"{'✅' if s['active'] else '⛔'} {s['emoji']} {s['name']}",
        callback_data=f"adm_svc:{s['id']}")]
            for s in db.list_services(active_only=False)]
    rows.append([InlineKeyboardButton("➕ Ajouter un service", callback_data="adm_addsvc")])
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="adm_panel")])
    return InlineKeyboardMarkup(rows)


def service_admin_keyboard(service_id):
    svc = db.get_service(service_id)
    rows = [[InlineKeyboardButton(
        f"{'✅' if o['active'] else '⛔'} {o['name']}", callback_data=f"adm_off:{o['id']}")]
            for o in db.list_offers(service_id, active_only=False)]
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
        [InlineKeyboardButton("🔐 Ajouter des codes", callback_data=f"adm_inventory:{offer_id}")],
        [InlineKeyboardButton("💵 Modifier le prix", callback_data=f"adm_setprice:{offer_id}"),
         InlineKeyboardButton("📦 Modifier le stock", callback_data=f"adm_setstock:{offer_id}")],
        [InlineKeyboardButton("✏️ Modifier le nom", callback_data=f"adm_offname:{offer_id}"),
         InlineKeyboardButton("📝 Modifier la note", callback_data=f"adm_offnote:{offer_id}")],
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
