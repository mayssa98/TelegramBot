"""
HEAVENPREM — Bot Telegram de vente de services numériques.
Point d'entrée principal. Exécuté en long polling pour rester réactif 24/7.
"""
import logging
import asyncio
import os
import html

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters,
)

import database as db
import keyboards as kb
import admin
from payment_verifier import verify_payment
from i18n import t, status_label
from config import (
    BOT_TOKEN, ADMIN_ID, BINANCE_PAY_ID, SHOP_NAME, CURRENCY, DEFAULT_LANG,
    AFFILIATE_TARGET, AFFILIATE_REWARD_CENTS,
)

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("logs/bot.log"), logging.StreamHandler()],
)
log = logging.getLogger("bot")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# états utilisateurs en mémoire (clé = user_id)
# "await_txid": order_id  |  "adm_setprice": offer_id  |  "adm_setstock": offer_id
#  "adm_deliver": order_id
PENDING = {}


async def audit_client_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Transmet à l'admin chaque message/commande reçu d'un client."""
    user = update.effective_user
    message = update.effective_message
    if not user or user.id == ADMIN_ID or not message:
        return
    content = message.text or message.caption or f"[{message.effective_attachment.__class__.__name__}]"
    content = html.escape(str(content)[:3000])
    identity = html.escape(user.full_name or "—")
    username = f"@{html.escape(user.username)}" if user.username else "sans username"
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"📨 <b>Interaction client</b>\n"
            f"👤 {identity} ({username})\n"
            f"🆔 <code>{user.id}</code>\n"
            f"💬 {content}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        log.warning("Impossible de notifier l'admin: %s", exc)


async def audit_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Transmet à l'admin chaque bouton pressé par un client."""
    query = update.callback_query
    user = query.from_user if query else None
    if not query or not user or user.id == ADMIN_ID:
        return
    identity = html.escape(user.full_name or "—")
    username = f"@{html.escape(user.username)}" if user.username else "sans username"
    label = ""
    if query.message and query.message.reply_markup:
        for row in query.message.reply_markup.inline_keyboard:
            for button in row:
                if button.callback_data == query.data:
                    label = button.text
                    break
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🖱 <b>Bouton client</b>\n"
            f"👤 {identity} ({username})\n"
            f"🆔 <code>{user.id}</code>\n"
            f"🔘 {html.escape(label or query.data or '—')}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        log.warning("Impossible de notifier l'admin: %s", exc)


def lang_of(user_id):
    return db.get_user_lang(user_id) or DEFAULT_LANG


# ---------------- /start ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    is_new = db.upsert_user(u.id, u.username or "", u.first_name or "")
    if is_new and context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0][4:])
            result = db.register_referral(
                u.id, referrer_id, AFFILIATE_TARGET, AFFILIATE_REWARD_CENTS
            )
            if result["accepted"]:
                ref_lang = lang_of(referrer_id)
                if result["rewarded"]:
                    await context.bot.send_message(
                        referrer_id,
                        t(ref_lang, "affiliate_rewarded", count=result["referrals"],
                          reward=f"{AFFILIATE_REWARD_CENTS / 100:.2f}"),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                else:
                    await context.bot.send_message(
                        referrer_id,
                        f"👥 Nouveau filleul ! Progression : "
                        f"{result['progress']}/{AFFILIATE_TARGET}.",
                    )
        except (ValueError, TypeError):
            pass
    lang = db.get_user_lang(u.id)
    if not lang:
        await update.message.reply_text(t(DEFAULT_LANG, "choose_lang"),
                                        reply_markup=kb.lang_keyboard())
    else:
        await send_main_menu(update, context, lang)


async def send_main_menu(update, context, lang, chat_id=None):
    uid = update.effective_user.id if update.effective_user else chat_id
    text = t(lang, "welcome", shop=SHOP_NAME)
    target = update.message or (update.callback_query.message if update.callback_query else None)
    if target:
        await target.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                reply_markup=kb.main_menu_keyboard(lang, uid))
    else:
        await context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=kb.main_menu_keyboard(lang, uid))


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    await update.message.reply_text(
        "🛠️ *Panneau Admin*", parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin.admin_panel_keyboard(),
    )


async def show_affiliate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = lang_of(user_id)
    me = context.bot.username or (await context.bot.get_me()).username
    link = f"https://t.me/{me}?start=ref_{user_id}"
    stats = db.affiliate_stats(user_id, AFFILIATE_TARGET)
    reward = AFFILIATE_REWARD_CENTS / 100
    balance = stats["balance_cents"] / 100
    message = t(
        lang, "affiliate_title", count=stats["referrals"],
        progress=stats["progress"], target=AFFILIATE_TARGET,
        balance=f"{balance:.2f}", reward=f"{reward:.2f}", link=link,
    )
    share_text = {
        "fr": f"🎁 Rejoins {SHOP_NAME} avec mon lien : {link}",
        "en": f"🎁 Join {SHOP_NAME} with my link: {link}",
        "ar": f"🎁 انضم إلى {SHOP_NAME} عبر رابطي: {link}",
    }.get(lang, f"Join {SHOP_NAME}: {link}")
    await update.effective_message.reply_text(
        message, parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.affiliate_keyboard(lang, link, share_text),
    )


# ---------------- Sélection langue ----------------
async def cb_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    lang = q.data.split(":")[1]
    db.set_user_lang(q.from_user.id, lang)
    await q.answer()
    await q.edit_message_text(t(lang, "lang_set"))
    await context.bot.send_message(
        q.from_user.id, t(lang, "welcome", shop=SHOP_NAME),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.main_menu_keyboard(lang, q.from_user.id),
    )


# ---------------- Boutons du menu reply ----------------
async def on_text_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = lang_of(uid)
    text = update.message.text.strip()

    # 1) états de saisie en cours (txid, admin prix/stock/livraison)
    if uid in PENDING:
        await handle_pending_input(update, context, lang)
        return

    # 2) menu reply
    if text == t(lang, "menu_catalog"):
        await show_catalog(update, context, lang)
    elif text == t(lang, "menu_orders"):
        await show_my_orders(update, context, lang)
    elif text == t(lang, "menu_help"):
        await update.message.reply_text(t(lang, "help_text", shop=SHOP_NAME),
                                        parse_mode=ParseMode.MARKDOWN)
    elif text == t(lang, "menu_lang"):
        await update.message.reply_text(t(lang, "choose_lang"),
                                        reply_markup=kb.lang_keyboard())
    elif text == t(lang, "menu_affiliate"):
        await show_affiliate(update, context)
    elif text == t(lang, "menu_admin") and uid == ADMIN_ID:
        await update.message.reply_text("🛠️ *Panneau Admin*", parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=admin.admin_panel_keyboard())
    else:
        # message libre non reconnu -> renvoyer menu
        await send_main_menu(update, context, lang)


# ---------------- Catalogue (client) ----------------
async def show_catalog(update, context, lang):
    text = t(lang, "catalog_title", shop=SHOP_NAME)
    msg = update.message or update.callback_query.message
    await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                         reply_markup=kb.services_keyboard(lang))


async def cb_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    lang = lang_of(uid)
    data = q.data
    await q.answer()

    if data == "home":
        await q.message.reply_text(t(lang, "welcome", shop=SHOP_NAME),
                                   parse_mode=ParseMode.MARKDOWN,
                                   reply_markup=kb.main_menu_keyboard(lang, uid))
        return
    if data == "catalog":
        await q.edit_message_text(t(lang, "catalog_title", shop=SHOP_NAME),
                                  parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=kb.services_keyboard(lang))
        return
    if data.startswith("svc:"):
        sid = int(data.split(":")[1])
        svc = db.get_service(sid)
        offers = db.list_offers(sid)
        if not offers:
            await q.edit_message_text(t(lang, "no_offers"),
                                      reply_markup=kb.services_keyboard(lang))
            return
        await q.edit_message_text(
            t(lang, "service_title", emoji=svc["emoji"], name=svc["name"]),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.offers_keyboard(lang, sid),
        )
        return
    if data.startswith("off:"):
        oid = int(data.split(":")[1])
        off = db.get_offer(oid)
        svc = db.get_service(off["service_id"])
        price = t(lang, "price_tbd") if off["price"] is None else f"{off['price']:.2f}"
        note = f"📝 {off['note']}" if off["note"] else ""
        await q.edit_message_text(
            t(lang, "offer_detail", emoji=svc["emoji"], service=svc["name"],
              offer=off["name"], price=price, cur=CURRENCY, stock=off["stock"], note=note),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.offer_detail_keyboard(lang, off),
        )
        return
    if data.startswith("buy:"):
        await handle_buy(update, context, lang)
        return
    if data.startswith("paid:"):
        oid = int(data.split(":")[1])
        PENDING[uid] = ("await_txid", oid)
        await q.message.reply_text(t(lang, "ask_txid", oid=oid),
                                   parse_mode=ParseMode.MARKDOWN)
        return


# ---------------- Achat ----------------
async def handle_buy(update, context, lang):
    q = update.callback_query
    uid = q.from_user.id
    oid_offer = int(q.data.split(":")[1])
    offer = db.get_offer(oid_offer)
    if not offer or offer["price"] is None or offer["stock"] <= 0:
        await q.answer(t(lang, "out_of_stock"), show_alert=True)
        return
    order_id = db.create_order(uid, offer, qty=1)
    order = db.get_order(order_id)
    text = t(lang, "order_created", oid=order_id, service=order["service_name"],
             offer=order["offer_name"], qty=order["qty"],
             total=f"{order['total_price']:.2f}", cur=CURRENCY,
             binance_id=BINANCE_PAY_ID)
    await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                               reply_markup=kb.paid_keyboard(lang, order_id))


# ---------------- Saisie en attente (txid / admin) ----------------
async def handle_pending_input(update, context, lang):
    uid = update.effective_user.id
    kind, ref = PENDING.get(uid)
    text = update.message.text.strip()

    if kind == "await_txid":
        await process_txid(update, context, lang, ref, text)
        PENDING.pop(uid, None)
        return

    # --- Admin : prix ---
    if kind == "adm_setprice" and uid == ADMIN_ID:
        try:
            price = float(text.replace(",", "."))
            if price < 0:
                raise ValueError
            db.update_offer(ref, price=price)
            await update.message.reply_text(f"✅ Prix mis à jour : {price:.2f}{CURRENCY}")
        except ValueError:
            await update.message.reply_text("⚠️ Valeur invalide. Envoyez un nombre, ex : 1.99")
            return
        PENDING.pop(uid, None)
        await update.message.reply_text("🛠️ *Panneau Admin*", parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=admin.admin_panel_keyboard())
        return

    # --- Admin : stock ---
    if kind == "adm_setstock" and uid == ADMIN_ID:
        try:
            stock = int(text)
            if stock < 0:
                raise ValueError
            db.update_offer(ref, stock=stock)
            await update.message.reply_text(f"✅ Stock mis à jour : {stock}")
        except ValueError:
            await update.message.reply_text("⚠️ Valeur invalide. Envoyez un entier, ex : 25")
            return
        PENDING.pop(uid, None)
        await update.message.reply_text("🛠️ *Panneau Admin*", parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=admin.admin_panel_keyboard())
        return

    if uid == ADMIN_ID and kind in {"adm_svcname", "adm_svcemoji", "adm_offname", "adm_offnote"}:
        if kind != "adm_offnote" and not text:
            await update.message.reply_text("⚠️ La valeur ne peut pas être vide.")
            return
        if kind == "adm_svcname":
            db.update_service(ref, name=text[:80])
        elif kind == "adm_svcemoji":
            db.update_service(ref, emoji=text[:12])
        elif kind == "adm_offname":
            db.update_offer(ref, name=text[:120])
        else:
            db.update_offer(ref, note=text[:250])
        PENDING.pop(uid, None)
        await update.message.reply_text("✅ Modification enregistrée.",
                                        reply_markup=admin.admin_panel_keyboard())
        return

    if kind == "adm_addsvc" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|", 1)]
        name, emoji = parts[0], parts[1] if len(parts) > 1 else "📦"
        if not name:
            await update.message.reply_text("⚠️ Format : Nom du service | emoji")
            return
        db.add_service(name[:80], emoji[:12])
        PENDING.pop(uid, None)
        await update.message.reply_text("✅ Service ajouté.", reply_markup=admin.admin_panel_keyboard())
        return

    if kind == "adm_addoff" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 3:
            await update.message.reply_text("⚠️ Format : Nom | prix | stock | note optionnelle")
            return
        try:
            price = float(parts[1].replace(",", "."))
            stock = int(parts[2])
            if price < 0 or stock < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Prix ou stock invalide.")
            return
        note = parts[3][:250] if len(parts) > 3 else ""
        db.add_offer(ref, parts[0][:120], price, stock, note)
        PENDING.pop(uid, None)
        await update.message.reply_text("✅ Offre ajoutée.", reply_markup=admin.admin_panel_keyboard())
        return

    # --- Admin : livraison ---
    if kind == "adm_deliver" and uid == ADMIN_ID:
        await deliver_order(update, context, ref, text)
        PENDING.pop(uid, None)
        return


# ---------------- Traitement de l'ID de transaction ----------------
async def process_txid(update, context, lang, order_id, txid):
    uid = update.effective_user.id
    order = db.get_order(order_id)
    if not order or order["user_id"] != uid:
        await update.message.reply_text(t(lang, "not_for_you"))
        return
    if len(txid) < 6:
        await update.message.reply_text(t(lang, "txid_too_short"))
        PENDING[uid] = ("await_txid", order_id)  # garder l'état
        return

    db.update_order(order_id, txid=txid, status="awaiting_verification")
    await update.message.reply_text(t(lang, "verifying"))

    # Vérification automatique (peut être longue) -> exécutée en thread
    result = await asyncio.to_thread(
        verify_payment, txid, order["total_price"], CURRENCY, order["created_at"]
    )

    if result["status"] == "confirmed" and db.mark_order_paid(order_id, "auto"):
        await update.message.reply_text(t(lang, "verify_ok", oid=order_id),
                                        parse_mode=ParseMode.MARKDOWN)
        await admin.notify_new_order(context, db.get_order(order_id))
    else:
        db.update_order(order_id, status="pending_payment", txid="",
                        verify_method="auto_failed")
        await update.message.reply_text(t(lang, "verify_failed", oid=order_id),
                                        parse_mode=ParseMode.MARKDOWN)

# ---------------- Mes commandes ----------------
async def show_my_orders(update, context, lang):
    uid = update.effective_user.id
    orders = db.list_user_orders(uid, limit=15)
    if not orders:
        await update.message.reply_text(t(lang, "no_orders"))
        return
    lines = [t(lang, "my_orders_title")]
    for o in orders:
        lines.append(t(lang, "order_line", oid=o["id"], offer=o["offer_name"],
                       total=f"{o['total_price']:.2f}", cur=CURRENCY,
                       status=status_label(lang, o["status"])))
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ================= ADMIN CALLBACKS =================
async def cb_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    if uid != ADMIN_ID:
        await q.answer("⛔", show_alert=True)
        return
    data = q.data
    await q.answer()

    if data == "adm_panel":
        await q.edit_message_text("🛠️ *Panneau Admin*", parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=admin.admin_panel_keyboard())
        return

    if data.startswith("adm_list:"):
        status = data.split(":")[1]
        keyboard, orders = admin.orders_list_keyboard(status)
        await q.edit_message_text(f"📋 Commandes — *{status}* ({len(orders)})",
                                  parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        return

    if data.startswith("adm_order:"):
        oid = int(data.split(":")[1])
        o = db.get_order(oid)
        await q.edit_message_text(admin.order_detail_text(o), parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=admin.order_detail_keyboard(o))
        return

    if data.startswith("adm_deliver:"):
        oid = int(data.split(":")[1])
        PENDING[uid] = ("adm_deliver", oid)
        await q.message.reply_text(
            f"🎁 Envoyez le contenu à livrer pour la commande #{oid} "
            f"(compte / code / instructions). Il sera transmis au client.")
        return

    # ---- gestion catalogue ----
    if data == "adm_catalog":
        await q.edit_message_text("📦 *Gestion catalogue* — choisissez un service :",
                                  parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=admin.catalog_admin_keyboard())
        return
    if data == "adm_addsvc":
        PENDING[uid] = ("adm_addsvc", 0)
        await q.message.reply_text("➕ Envoyez : `Nom du service | emoji`\nExemple : `Netflix | 🎬`",
                                   parse_mode=ParseMode.MARKDOWN)
        return
    if data.startswith("adm_addoff:"):
        sid = int(data.split(":")[1])
        PENDING[uid] = ("adm_addoff", sid)
        await q.message.reply_text(
            "➕ Envoyez : `Nom | prix | stock | note`\nExemple : `Premium 1 mois | 4.99 | 20 | Garantie 30 jours`",
            parse_mode=ParseMode.MARKDOWN)
        return
    if data.startswith("adm_svcname:") or data.startswith("adm_svcemoji:"):
        action, sid = data.split(":")
        kind = "adm_svcname" if action == "adm_svcname" else "adm_svcemoji"
        PENDING[uid] = (kind, int(sid))
        await q.message.reply_text("✏️ Envoyez la nouvelle valeur :")
        return
    if data.startswith("adm_svctoggle:"):
        sid = int(data.split(":")[1])
        svc = db.get_service(sid)
        db.update_service(sid, active=0 if svc["active"] else 1)
        await q.edit_message_text("✅ Statut du service modifié.",
                                  reply_markup=admin.catalog_admin_keyboard())
        return
    if data.startswith("adm_svcdel:"):
        sid = int(data.split(":")[1])
        db.archive_service(sid)
        await q.edit_message_text("🗑 Service archivé avec ses offres.",
                                  reply_markup=admin.catalog_admin_keyboard())
        return
    if data.startswith("adm_svc:"):
        sid = int(data.split(":")[1])
        svc = db.get_service(sid)
        await q.edit_message_text(f"📦 *{svc['name']}* — offres :",
                                  parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=admin.service_admin_keyboard(sid))
        return
    if data.startswith("adm_off:") or data.startswith("adm_off_back:"):
        oid = int(data.split(":")[1])
        off = db.get_offer(oid)
        price = "—" if off["price"] is None else f"{off['price']:.2f}{CURRENCY}"
        await q.edit_message_text(
            f"🧩 *{off['name']}*\n💵 Prix : {price}\n📦 Stock : {off['stock']}\n📝 {off['note'] or '—'}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin.offer_admin_keyboard(oid))
        return
    if data.startswith("adm_offname:") or data.startswith("adm_offnote:"):
        action, oid = data.split(":")
        PENDING[uid] = ("adm_offname" if action == "adm_offname" else "adm_offnote", int(oid))
        await q.message.reply_text("✏️ Envoyez la nouvelle valeur :")
        return
    if data.startswith("adm_offtoggle:"):
        oid = int(data.split(":")[1])
        off = db.get_offer(oid)
        db.update_offer(oid, active=0 if off["active"] else 1)
        await q.edit_message_text("✅ Statut de l'offre modifié.",
                                  reply_markup=admin.service_admin_keyboard(off["service_id"]))
        return
    if data.startswith("adm_offdel:"):
        oid = int(data.split(":")[1])
        off = db.get_offer(oid)
        db.archive_offer(oid)
        await q.edit_message_text("🗑 Offre archivée.",
                                  reply_markup=admin.service_admin_keyboard(off["service_id"]))
        return
    if data.startswith("adm_setprice:"):
        oid = int(data.split(":")[1])
        PENDING[uid] = ("adm_setprice", oid)
        await q.message.reply_text("💵 Envoyez le nouveau prix (ex : 1.99) :")
        return
    if data.startswith("adm_setstock:"):
        oid = int(data.split(":")[1])
        PENDING[uid] = ("adm_setstock", oid)
        await q.message.reply_text("📦 Envoyez le nouveau stock (entier, ex : 25) :")
        return


async def deliver_order(update, context, order_id, content):
    o = db.get_order(order_id)
    if not o:
        await update.message.reply_text("Commande introuvable.")
        return
    db.update_order(order_id, status="delivered", delivery_text=content)
    cl = lang_of(o["user_id"])
    try:
        await context.bot.send_message(
            o["user_id"],
            t(cl, "delivery_received", oid=order_id, service=o["service_name"],
              offer=o["offer_name"], content=content),
            parse_mode=ParseMode.MARKDOWN,
        )
        await update.message.reply_text(f"✅ Commande #{order_id} livrée au client.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Échec d'envoi au client : {e}")


async def notify_client(context, user_id, key, **kwargs):
    cl = lang_of(user_id)
    try:
        await context.bot.send_message(user_id, t(cl, key, **kwargs),
                                       parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


# ---------------- Erreurs ----------------
async def on_error(update, context):
    log.error("Update error: %s", context.error)


def build_app():
    if not BOT_TOKEN:
        raise RuntimeError("HP_BOT_TOKEN doit être défini dans les variables d'environnement")
    db.init_db()
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    # Groupe -1 : audit non bloquant avant les handlers fonctionnels du groupe 0.
    app.add_handler(CallbackQueryHandler(audit_client_callback), group=-1)
    app.add_handler(MessageHandler(filters.ALL, audit_client_message), group=-1)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", lambda u, c: send_main_menu(u, c, lang_of(u.effective_user.id))))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("affiliate", show_affiliate))
    app.add_handler(CallbackQueryHandler(cb_lang, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(cb_admin, pattern=r"^adm_"))
    app.add_handler(CallbackQueryHandler(cb_navigation))  # reste
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_menu))
    app.add_error_handler(on_error)
    return app


def main():
    app = build_app()
    log.info("HEAVENPREM bot démarré (long polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
