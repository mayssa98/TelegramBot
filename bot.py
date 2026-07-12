"""
HEAVENPREM — Bot Telegram de vente de services numériques.
Point d'entrée principal. Exécuté en long polling pour rester réactif 24/7.
"""
import asyncio
import contextlib
import html
import logging
import os

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import admin
import database as db
import keyboards as kb
from app.domain import order_service, payment_service, support_service
from config import (
    ADMIN_ID,
    AFFILIATE_REWARD_CENTS,
    AFFILIATE_TARGET,
    BINANCE_PAY_ID,
    BOT_TOKEN,
    CURRENCY,
    DEFAULT_LANG,
    SHOP_NAME,
)
from i18n import status_label, t

_handlers = [logging.StreamHandler()]
if not os.environ.get("VERCEL"):
    os.makedirs("logs", exist_ok=True)
    _handlers.insert(0, logging.FileHandler("logs/bot.log"))
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
    handlers=_handlers,
)
log = logging.getLogger("bot")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# états utilisateurs en mémoire (clé = user_id)
# "await_txid": order_id  |  "adm_setprice": offer_id  |  "adm_setstock": offer_id
#  "adm_deliver": order_id
class PendingStates:
    """Small mapping facade backed by MongoDB for serverless-safe conversations."""
    def __contains__(self, user_id):
        return db.get_pending_state(user_id) is not None

    def __setitem__(self, user_id, state):
        db.set_pending_state(user_id, state)

    def get(self, user_id, default=None):
        return db.get_pending_state(user_id) or default

    def pop(self, user_id, default=None):
        return db.pop_pending_state(user_id, default)


PENDING = PendingStates()


async def block_banned_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and user.id != ADMIN_ID and db.is_user_banned(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔ Accès suspendu.", show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text("⛔ Votre accès à cette boutique est suspendu.")
        raise ApplicationHandlerStop


async def block_maintenance_purchases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable only new purchases while keeping orders and support available."""
    user = update.effective_user
    if not user or user.id == ADMIN_ID or not update.callback_query:
        return
    settings = db.shop_settings()
    if settings["maintenance_enabled"]:
        await update.callback_query.answer(settings["maintenance_message"], show_alert=True)
        raise ApplicationHandlerStop





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


async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_user.id)
    PENDING[update.effective_user.id] = ("support", 0)
    await update.message.reply_text(t(lang, "support_prompt"))


async def cmd_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_catalog(update, context, lang_of(update.effective_user.id))


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_my_orders(update, context, lang_of(update.effective_user.id))


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_user.id)
    await update.effective_message.reply_text(t(lang, "choose_lang"), reply_markup=kb.lang_keyboard())


async def cmd_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_user.id)
    await update.effective_message.reply_text(t(lang, "terms_text"), parse_mode=ParseMode.MARKDOWN)


async def cmd_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_user.id)
    await update.effective_message.reply_text(t(lang, "privacy_text"), parse_mode=ParseMode.MARKDOWN)


async def show_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = lang_of(uid)
    account = db.user_account_summary(uid)
    labels = {
        "fr": ("Mon compte BlackMarket", "Nom", "Utilisateur", "Commandes", "Paiements validés", "Total payé", "Historique récent"),
        "en": ("My BlackMarket account", "Name", "Username", "Orders", "Validated payments", "Total paid", "Recent history"),
        "ar": ("حساب BlackMarket", "الاسم", "المستخدم", "الطلبات", "المدفوعات المؤكدة", "إجمالي المدفوع", "السجل الأخير"),
    }[lang if lang in ("fr", "en", "ar") else "fr"]
    name = html.escape(str(account.get("first_name") or update.effective_user.full_name or "—"))
    username = html.escape("@" + account["username"] if account.get("username") else "—")
    lines = [f"👤 <b>{labels[0]}</b>", "", f"🪪 <b>{labels[1]}:</b> {name}",
             f"🔗 <b>{labels[2]}:</b> {username}", f"🧾 <b>{labels[3]}:</b> {account['order_count']}",
             f"✅ <b>{labels[4]}:</b> {account['paid_count']}", f"💰 <b>{labels[5]}:</b> {account['total_paid']:.2f} {CURRENCY}",
             "", f"📚 <b>{labels[6]}:</b>"]
    if account["orders"]:
        for order in account["orders"][:10]:
            lines.append(f"• #{order['id']} — {html.escape(str(order['offer_name']))} — {order['total_price']:.2f} {CURRENCY} — {html.escape(status_label(lang, order['status']))}")
    else:
        lines.append("—")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML,
                                              reply_markup=kb.main_menu_keyboard(lang, uid))


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
    elif text == t(lang, "menu_account"):
        await show_account(update, context)
    elif text == t(lang, "menu_help"):
        await update.message.reply_text(t(lang, "help_text", shop=SHOP_NAME),
                                        parse_mode=ParseMode.MARKDOWN)
    elif text == t(lang, "menu_lang"):
        await update.message.reply_text(t(lang, "choose_lang"),
                                        reply_markup=kb.lang_keyboard())
    elif text == t(lang, "menu_affiliate"):
        await show_affiliate(update, context)
    elif text == t(lang, "menu_support"):
        await cmd_support(update, context)
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
        await handle_buy_confirmation(update, context, lang)
        return
    if data.startswith("confirm_buy:"):
        await handle_buy_confirmed(update, context, lang)
        return
    if data.startswith("cancel_buy:"):
        await q.edit_message_text(t(lang, "cancelled_msg"))
        return
    if data.startswith("paid:"):
        oid = int(data.split(":")[1])
        PENDING[uid] = ("await_txid", oid)
        await q.message.reply_text(t(lang, "ask_txid", oid=oid),
                                   parse_mode=ParseMode.MARKDOWN)
        return
    if data.startswith("continue_pay:"):
        oid = int(data.split(":")[1])
        order = db.get_order(oid)
        if order and order["user_id"] == uid:
            text = t(lang, "order_created", oid=oid, service=order["service_name"],
                     offer=order["offer_name"], qty=order["qty"],
                     total=f"{order['total_price']:.2f}", cur=CURRENCY,
                     binance_id=BINANCE_PAY_ID)
            await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=kb.paid_keyboard(lang, oid))
        return
    if data.startswith("delivery_ok:"):
        order_id = int(data.split(":")[1])
        order = db.get_order(order_id)
        if not order or order.get("user_id") != uid:
            await q.answer(t(lang, "not_for_you"), show_alert=True)
            return
        db.audit_event("order.delivery_confirmed", actor_id=uid, details={"order_id": order_id})
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(t(lang, "delivery_confirmed"))
        return
    if data.startswith("delivery_problem:"):
        order_id = int(data.split(":")[1])
        order = db.get_order(order_id)
        if not order or order.get("user_id") != uid:
            await q.answer(t(lang, "not_for_you"), show_alert=True)
            return
        PENDING[uid] = ("support_order", order_id)
        await q.message.reply_text(t(lang, "support_order_prompt", oid=order_id))
        return


# ---------------- Confirmation avant achat ----------------
async def handle_buy_confirmation(update, context, lang):
    """Affiche un résumé avant de créer la commande."""
    q = update.callback_query
    uid = q.from_user.id
    offer_id = int(q.data.split(":")[1])
    offer = db.get_offer(offer_id)

    if not offer or offer["price"] is None or offer["stock"] <= 0:
        await q.answer(t(lang, "out_of_stock"), show_alert=True)
        return

    # Vérifier s'il y a déjà une commande pending pour cette offre
    existing = order_service.check_duplicate_pending_order(uid, offer_id)
    if existing:
        await q.edit_message_text(
            t(lang, "duplicate_order", oid=existing["id"],
              offer=existing["offer_name"],
              total=f"{existing['total_price']:.2f}", cur=CURRENCY),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.duplicate_order_keyboard(lang, existing["id"], offer_id),
        )
        return

    svc = db.get_service(offer["service_id"])
    # Afficher le résumé de confirmation
    await q.edit_message_text(
        t(lang, "confirm_purchase",
          emoji=svc["emoji"] if svc else "📦",
          service=svc["name"] if svc else "",
          offer=offer["name"],
          price=f"{offer['price']:.2f}",
          cur=CURRENCY,
          qty=1,
          total=f"{offer['price']:.2f}"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.confirm_buy_keyboard(lang, offer_id),
    )


async def handle_buy_confirmed(update, context, lang):
    """Crée la commande après confirmation de l'utilisateur."""
    q = update.callback_query
    uid = q.from_user.id
    offer_id = int(q.data.split(":")[1])
    offer = db.get_offer(offer_id)

    if not offer or offer["price"] is None or offer["stock"] <= 0:
        await q.answer(t(lang, "out_of_stock"), show_alert=True)
        return

    try:
        order = order_service.create_order(uid, offer, qty=1)
    except ValueError as exc:
        await q.answer(str(exc), show_alert=True)
        return

    text = t(lang, "order_created", oid=order["id"], service=order["service_name"],
             offer=order["offer_name"], qty=order["qty"],
             total=f"{order['total_price']:.2f}", cur=CURRENCY,
             binance_id=BINANCE_PAY_ID)
    await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                              reply_markup=kb.paid_keyboard(lang, order["id"]))


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
            await update.message.reply_text(f"✅ Prix mis à jour : {price:.2f} {CURRENCY}")
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

    if kind == "adm_inventory" and uid == ADMIN_ID:
        items = [line.strip() for line in text.splitlines() if line.strip()]
        try:
            added = db.add_inventory_items(ref, items)
        except RuntimeError as exc:
            await update.message.reply_text(f"⚠️ {exc}")
            return
        PENDING.pop(uid, None)
        stats = db.inventory_stats(ref)
        await update.message.reply_text(
            f"✅ {added} code(s) ajouté(s) et chiffré(s).\n"
            f"Disponible : {stats['available']} • Vendus : {stats['sold']}",
            reply_markup=admin.offer_admin_keyboard(ref),
        )
        return

    if kind == "support":
        ticket = support_service.create_ticket(uid, text)
        PENDING[uid] = ("ticket_message", ticket["id"])
        await update.message.reply_text(t(lang, "ticket_created", tid=ticket["id"]))
        await context.bot.send_message(
            ADMIN_ID,
            f"🎫 Nouveau ticket #{ticket['id']}\nUtilisateur: <code>{uid}</code>\n\n{html.escape(text[:2000])}",
            parse_mode=ParseMode.HTML,
        )
        return

    if kind == "support_order":
        ticket = support_service.create_ticket(
            uid,
            text,
            category="delivery",
            order_id=int(ref),
            priority="high",
        )
        PENDING[uid] = ("ticket_message", ticket["id"])
        await update.message.reply_text(t(lang, "ticket_created", tid=ticket["id"]))
        await context.bot.send_message(
            ADMIN_ID,
            f"⚠️ Ticket livraison #{ticket['id']} — commande #{ref}\nUtilisateur: <code>{uid}</code>\n\n{html.escape(text[:2000])}",
            parse_mode=ParseMode.HTML,
        )
        return

    if kind == "ticket_message":
        ticket = support_service.get_ticket(int(ref))
        if not ticket or ticket.get("user_id") != uid or ticket.get("status") == "closed":
            PENDING.pop(uid, None)
            await update.message.reply_text(t(lang, "ticket_unavailable"))
            return
        support_service.add_message(int(ref), uid, text, sender_type="client")
        await update.message.reply_text(t(lang, "ticket_message_added", tid=ref))
        await context.bot.send_message(
            ADMIN_ID,
            f"💬 Réponse client — ticket #{ref}\nUtilisateur: <code>{uid}</code>\n\n{html.escape(text[:2000])}",
            parse_mode=ParseMode.HTML,
        )
        return

    # --- Admin : livraison ---
    if kind == "adm_deliver" and uid == ADMIN_ID:
        await deliver_order(update, context, ref, text)
        PENDING.pop(uid, None)
        return


# ---------------- Traitement de l'ID de transaction ----------------
async def process_txid(update, context, lang, order_id, txid):
    uid = update.effective_user.id

    await update.message.reply_text(t(lang, "verifying"))

    # Vérification via le service de paiement (idempotent)
    result = await asyncio.to_thread(
        payment_service.submit_payment, order_id, txid, uid
    )

    if result["status"] in ("delivered", "confirmed", "confirmed_no_delivery"):
        if result["delivered_content"]:
            content = "\n\n".join(result["delivered_content"])
            paid_order = db.get_order(order_id)
            await update.message.reply_text(
                t(lang, "delivery_received", oid=order_id,
                  service=paid_order["service_name"], offer=paid_order["offer_name"],
                  content=html.escape(content)),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.post_delivery_keyboard(lang, order_id),
            )
        else:
            await update.message.reply_text(t(lang, "verify_ok", oid=order_id),
                                            parse_mode=ParseMode.MARKDOWN)
            await admin.notify_new_order(context, db.get_order(order_id))
    elif result["status"] == "already_paid":
        await update.message.reply_text(t(lang, "already_paid", oid=order_id),
                                        parse_mode=ParseMode.MARKDOWN)
    else:
        error_code = result.get("error_code", "unknown")
        if error_code == "too_short":
            await update.message.reply_text(t(lang, "txid_too_short"))
            PENDING[uid] = ("await_txid", order_id)  # garder l'état
            return
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
    if data == "adm_tickets":
        markup, tickets = admin.tickets_keyboard()
        await q.edit_message_text(f"🎫 Tickets ouverts ({len(tickets)})", reply_markup=markup)
        return
    if data.startswith("adm_ticket:"):
        ticket = db.get_ticket(int(data.split(":")[1]))
        if ticket:
            await q.edit_message_text(
                f"🎫 Ticket #{ticket['id']}\nUtilisateur: `{ticket['user_id']}`\n"
                f"Statut: `{ticket['status']}`\n\n{ticket['message']}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=admin.admin_panel_keyboard(),
            )
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
    if data.startswith("adm_inventory:"):
        oid = int(data.split(":")[1])
        PENDING[uid] = ("adm_inventory", oid)
        stats = db.inventory_stats(oid)
        await q.message.reply_text(
            "🔐 Envoyez un code/compte par ligne. Ils seront chiffrés avant stockage.\n"
            f"Actuellement disponibles : {stats['available']}"
        )
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
        price = "—" if off["price"] is None else f"{off['price']:.2f} {CURRENCY}"
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
    with contextlib.suppress(Exception):
        await context.bot.send_message(user_id, t(cl, key, **kwargs),
                                       parse_mode=ParseMode.MARKDOWN)


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
    # Groupe -2 : blocage des utilisateurs bannis avant les handlers du groupe 0.
    app.add_handler(MessageHandler(filters.ALL, block_banned_users), group=-2)
    app.add_handler(CallbackQueryHandler(block_banned_users), group=-2)
    app.add_handler(
        CallbackQueryHandler(block_maintenance_purchases, pattern=r"^(buy|confirm_buy):"),
        group=-1,
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", lambda u, c: send_main_menu(u, c, lang_of(u.effective_user.id))))
    app.add_handler(CommandHandler("catalog", cmd_catalog))
    app.add_handler(CommandHandler("orders", cmd_orders))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("support", cmd_support))
    app.add_handler(CommandHandler("account", show_account))
    app.add_handler(CommandHandler("language", cmd_language))
    app.add_handler(CommandHandler("affiliate", show_affiliate))
    app.add_handler(CommandHandler("terms", cmd_terms))
    app.add_handler(CommandHandler("privacy", cmd_privacy))
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
