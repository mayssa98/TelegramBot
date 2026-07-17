"""
HEAVENPREM — Bot Telegram de vente de services numériques.
Point d'entrée principal. Exécuté en long polling pour rester réactif 24/7.
"""
import asyncio
import contextlib
import html
import io
import logging
import os
import re
from datetime import UTC, datetime

from telegram import InputFile, Update
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
from app.domain import (
    affiliate_service,
    inventory_service,
    loyalty_service,
    order_service,
    payment_service,
    support_service,
    wallet_service,
)
from config import (
    ADMIN_ID,
    AFFILIATE_DAILY_CAP,
    AFFILIATE_FIVE_REWARD_CENTS,
    AFFILIATE_QUALIFY_CENTS,
    AFFILIATE_TEN_REWARD_CENTS,
    BINANCE_PAY_ID,
    BOT_TOKEN,
    CURRENCY,
    DEFAULT_LANG,
    SHOP_NAME,
    configuration_issues,
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


def offer_detail_fields(description: str, note: str) -> dict[str, str]:
    fields = {
        "note": note or "Full warranty",
        "duration": "30 Days",
        "mail": "Included",
        "access": "Ready-made account",
        "description": "",
    }
    remaining = []
    aliases = {
        "warranty": "note",
        "duration": "duration",
        "mail": "mail",
        "email": "mail",
        "access": "access",
        "type": "access",
    }
    for raw_line in (description or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" in line:
            key, value = [part.strip() for part in line.split(":", 1)]
            normalized = key.lower().replace(" ", "_")
            target = aliases.get(normalized)
            if target and value:
                fields[target] = value
                continue
        remaining.append(line)
    fields["description"] = "\n".join(f"\u2022 {item}" for item in remaining)
    if not fields["description"]:
        fields["description"] = "\U0001f525 Premium benefits included"
    return fields


# ---------------- /start ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    is_new = db.upsert_user(u.id, u.username or "", u.first_name or "")
    if is_new and context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0][4:])
            affiliate_service.register_referral_link(u.id, referrer_id)
        except (ValueError, TypeError):
            pass
    lang = db.get_user_lang(u.id)
    if not lang:
        await update.message.reply_text(t(DEFAULT_LANG, "choose_lang"),
                                        reply_markup=kb.lang_keyboard())
    elif context.args and context.args[0] == "catalog":
        await show_catalog(update, context, lang)
    elif context.args and context.args[0] == "orders":
        await show_my_orders(update, context, lang)
    elif context.args and context.args[0] == "support":
        await cmd_support(update, context)
    else:
        await send_main_menu(update, context, lang)


async def send_main_menu(update, context, lang, chat_id=None):
    uid = update.effective_user.id if update.effective_user else chat_id
    configured = db.shop_settings().get("welcome_message", "").strip()
    text = configured or t(lang, "welcome", shop=SHOP_NAME)
    target = update.message or (update.callback_query.message if update.callback_query else None)
    markup = kb.home_keyboard(lang, uid)
    public_base_url = os.environ.get(
        "HP_PUBLIC_BASE_URL",
        "https://telegram-bot-mayssa98s-projects.vercel.app",
    ).rstrip("/")
    banner_source = (
        os.environ.get("HP_WELCOME_PHOTO_FILE_ID", "").strip()
        or f"{public_base_url}/assets/blackmarket-welcome-v2.png"
    )
    if target:
        try:
            await target.reply_photo(
                photo=banner_source,
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=markup,
            )
        except Exception:
            log.exception("Welcome image could not be sent; falling back to text")
            await target.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    else:
        try:
            await context.bot.send_photo(
                chat_id,
                photo=banner_source,
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=markup,
            )
        except Exception:
            log.exception("Welcome image could not be sent; falling back to text")
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)


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
    await update.effective_message.reply_text(
        t(lang, "support_admin_contact", admin="@Anwer_07"),
        parse_mode=ParseMode.HTML,
        reply_markup=kb.orders_keyboard(lang),
    )


async def cmd_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_catalog(update, context, lang_of(update.effective_user.id))


async def show_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = lang_of(uid)
    await update.effective_message.reply_text(
        t(lang, "topup_message", binance_id=BINANCE_PAY_ID, telegram_id=uid),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.topup_keyboard(lang),
    )


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_my_orders(update, context, lang_of(update.effective_user.id))


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_user.id)
    await update.effective_message.reply_text(t(lang, "choose_lang"), reply_markup=kb.lang_keyboard())


async def cmd_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_user.id)
    text = db.shop_settings().get("terms_message", "").strip() or t(lang, "terms_text")
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_user.id)
    text = db.shop_settings().get("privacy_message", "").strip() or t(lang, "privacy_text")
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def show_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = lang_of(uid)
    account = db.user_account_summary(uid)
    stats = affiliate_service.get_stats(uid)
    loyalty = loyalty_service.active_benefit(uid)
    wallet = stats["balance_cents"] / 100
    name = html.escape(str(account.get("first_name") or update.effective_user.full_name or "—"))
    username = html.escape("@" + account["username"] if account.get("username") else "—")
    level = loyalty["level"] or "—"
    expires = datetime.fromtimestamp(loyalty["expires_at"], UTC).strftime("%d/%m/%Y") if loyalty["expires_at"] else "—"
    text = t(
        lang, "profile_card", name=name, username=username, telegram_id=uid,
        wallet=f"{wallet:.2f}", invites=stats["referrals"],
        qualified=stats["qualified_referrals"], total_buy=f"{account['total_paid']:.2f}",
        level=level.title(), discount=loyalty["discount_percent"], expires=expires,
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML,
                                              reply_markup=kb.home_keyboard(lang, uid))


async def show_affiliate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = lang_of(user_id)
    me = context.bot.username or (await context.bot.get_me()).username
    link = f"https://t.me/{me}?start=ref_{user_id}"
    stats = affiliate_service.get_stats(user_id)
    balance = stats["balance_cents"] / 100
    earned = stats["earned_cents"] / 100
    message = t(
        lang, "affiliate_title", earned=f"{earned:.2f}", balance=f"{balance:.2f}",
        referrals=stats["referrals"], rewarded=stats["qualified_referrals"],
        pending=stats["pending_referrals"],
        five_reward=f"{AFFILIATE_FIVE_REWARD_CENTS / 100:.2f}",
        ten_reward=f"{AFFILIATE_TEN_REWARD_CENTS / 100:.2f}",
        qualify=f"{AFFILIATE_QUALIFY_CENTS / 100:.2f}",
        today=stats["qualified_today"], daily_cap=AFFILIATE_DAILY_CAP,
        link=link,
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
    await q.edit_message_text(
        t(lang, "onboarding_1", shop=SHOP_NAME),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.onboarding_keyboard(lang, 1),
    )


# ---------------- Boutons du menu reply ----------------
async def on_text_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = lang_of(uid)
    text = update.message.text.strip()
    pending = PENDING.get(uid)

    def clear_support_pending():
        if pending and pending[0].startswith(("support", "ticket_")):
            PENDING.pop(uid, None)

    blocking_states = {
        "await_txid",
        "await_topup_txid",
        "adm_setprice",
        "adm_setstock",
        "adm_svcname",
        "adm_svcemoji",
        "adm_offname",
        "adm_offnote",
        "adm_offdesc",
        "adm_offinstructions",
        "adm_offdelay",
        "adm_addsvc",
        "adm_addoff",
        "adm_inventory",
        "adm_deliver",
    }

    if text == t(lang, "menu_catalog"):
        clear_support_pending()
        await show_catalog(update, context, lang)
    elif text == t(lang, "menu_orders"):
        clear_support_pending()
        await show_my_orders(update, context, lang)
    elif text == t(lang, "menu_topup"):
        clear_support_pending()
        await show_topup(update, context)
    elif text == t(lang, "menu_account"):
        clear_support_pending()
        await show_account(update, context)
    elif text == t(lang, "menu_lang"):
        clear_support_pending()
        await update.message.reply_text(t(lang, "choose_lang"), reply_markup=kb.lang_keyboard())
    elif text == t(lang, "menu_affiliate"):
        clear_support_pending()
        await show_affiliate(update, context)
    elif text == t(lang, "menu_support"):
        await cmd_support(update, context)
    elif text == t(lang, "menu_admin") and uid == ADMIN_ID:
        clear_support_pending()
        await update.message.reply_text("\U0001f6e0\ufe0f *Panneau Admin*", parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=admin.admin_panel_keyboard())
    elif pending and (pending[0] in blocking_states or pending[0].startswith(("support", "ticket_"))):
        await handle_pending_input(update, context, lang)
    else:
        await send_main_menu(update, context, lang)


# ---------------- Catalogue (client) ----------------
async def show_catalog(update, context, lang):
    text = t(lang, "catalog_title", shop=SHOP_NAME)
    msg = update.message or update.callback_query.message
    await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                         reply_markup=kb.services_keyboard(lang))


async def show_callback_screen(query, text, *, reply_markup, parse_mode=ParseMode.MARKDOWN):
    """Render a callback screen from either a text message or a photo caption."""
    if getattr(query.message, "text", None):
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        return
    await query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    with contextlib.suppress(Exception):
        await query.edit_message_reply_markup(reply_markup=None)


async def cb_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    lang = lang_of(uid)
    data = q.data
    await q.answer()

    if data.startswith("tour:"):
        step = max(1, min(3, int(data.split(":", 1)[1])))
        await q.edit_message_text(
            t(lang, f"onboarding_{step}", shop=SHOP_NAME),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.onboarding_keyboard(lang, step),
        )
        return
    if data == "home":
        await send_main_menu(update, context, lang)
        return
    if data == "catalog":
        await show_callback_screen(
            q,
            t(lang, "catalog_title", shop=SHOP_NAME),
            reply_markup=kb.services_keyboard(lang),
        )
        return
    if data == "orders":
        await show_my_orders(update, context, lang)
        return
    if data == "topup":
        await show_topup(update, context)
        return
    if data == "topup_claim":
        PENDING[uid] = ("await_topup_txid", 0)
        await q.message.reply_text(t(lang, "topup_ask_txid"), parse_mode=ParseMode.MARKDOWN)
        return
    if data.startswith("orders_group:") or data == "orders_export:all":
        orders = db.list_user_orders(uid, limit=500)
        if not orders:
            await q.message.reply_text(t(lang, "no_orders"), reply_markup=kb.orders_keyboard(lang))
            return
        if data == "orders_export:all":
            await send_orders_export(q, lang, orders, t(lang, "orders_all_title"))
            return
        groups = order_service_groups(orders)
        index = int(data.split(":", 1)[1])
        if index < 0 or index >= len(groups):
            await q.answer(t(lang, "orders_group_unavailable"), show_alert=True)
            return
        group = groups[index]
        await send_orders_export(q, lang, group["orders"], group["name"])
        return
    if data == "account":
        await show_account(update, context)
        return
    if data == "affiliate":
        await show_affiliate(update, context)
        return
    if data == "affiliate_copy":
        me = context.bot.username or (await context.bot.get_me()).username
        link = f"https://t.me/{me}?start=ref_{uid}"
        await q.message.reply_text(t(lang, "affiliate_copy_message", link=link), parse_mode=ParseMode.MARKDOWN)
        return
    if data == "support":
        await cmd_support(update, context)
        return
    if data == "language":
        await q.message.reply_text(t(lang, "choose_lang"), reply_markup=kb.lang_keyboard())
        return
    if data.startswith("order_view:"):
        oid = int(data.split(":", 1)[1])
        order = db.get_order(oid)
        if not order or order.get("user_id") != uid:
            await q.answer(t(lang, "not_for_you"), show_alert=True)
            return
        await q.message.reply_text(
            t(lang, "order_card", oid=oid, offer=order["offer_name"], qty=order["qty"],
              total=f"{order['total_price']:.2f}", cur=CURRENCY,
              status=status_label(lang, order["status"])),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.orders_keyboard(lang),
        )
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
        note = off["note"] if off["note"] else ""
        description = off.get("description") or ""
        delivery = off.get("delivery_delay") or ""
        fields = offer_detail_fields(description, note)
        detail_text = t(lang, "offer_detail", emoji=svc["emoji"], service=svc["name"],
                        offer=off["name"], price=price, cur=off.get("currency", CURRENCY),
                        stock=off["stock"], note=fields["note"], description=fields["description"],
                        delivery=delivery or "Instantane apres confirmation",
                        duration=fields["duration"], mail=fields["mail"], access=fields["access"])
        is_chatgpt_offer = "chat" in off["name"].lower() and "gpt" in off["name"].lower()
        if is_chatgpt_offer:
            base_url = os.environ.get("HP_PUBLIC_BASE_URL", "https://telegram-bot-mayssa98s-projects.vercel.app").rstrip("/")
            await q.message.reply_photo(
                photo=f"{base_url}/assets/chatgpt-plus-benefits.png",
                caption="\U0001f525 *ChatGPT Plus Benefits*",
                parse_mode=ParseMode.MARKDOWN,
            )
            await q.message.reply_text(
                detail_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb.offer_detail_keyboard(lang, off),
            )
            with contextlib.suppress(Exception):
                await q.message.delete()
            return
        await q.edit_message_text(
            detail_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.offer_detail_keyboard(lang, off),
        )
        return
    if data.startswith("buy:"):
        await handle_quantity_selection(update, context, lang)
        return
    if data.startswith("qty_page:"):
        await handle_quantity_selection(update, context, lang)
        return
    if data.startswith("buyq:"):
        await handle_buy_confirmation(update, context, lang)
        return
    if data.startswith(("confirm_buy:", "pay_wallet:", "pay_binance:")):
        payment_method = "wallet" if data.startswith("pay_wallet:") else "binance"
        await handle_buy_confirmed(update, context, lang, payment_method=payment_method)
        return
    if data.startswith("cancel_buy:"):
        order_id = int(data.split(":", 1)[1])
        order = db.get_order(order_id)
        if order and order.get("user_id") == uid:
            order_service.cancel_order(order_id, reason="Cancelled by customer")
        await q.edit_message_text(t(lang, "cancelled_msg"))
        return
    if data.startswith("copy_binance_id:"):
        oid = int(data.split(":")[1])
        order = db.get_order(oid)
        if order and order["user_id"] == uid:
            await q.message.reply_text(
                t(lang, "copy_binance_id_msg", binance_id=BINANCE_PAY_ID),
                parse_mode=ParseMode.MARKDOWN,
            )
        return
    if data.startswith("copy_amount:"):
        oid = int(data.split(":")[1])
        order = db.get_order(oid)
        if order and order["user_id"] == uid:
            await q.message.reply_text(
                t(lang, "copy_amount_msg", total=f"{order['total_price']:.2f}", cur=CURRENCY),
                parse_mode=ParseMode.MARKDOWN,
            )
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
            payment_message = await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                                         reply_markup=kb.paid_keyboard(lang, oid))
            await run_auto_payment_check(payment_message, context, lang, oid, uid)
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
    if data.startswith("rate:"):
        order_id = int(data.split(":", 1)[1])
        order = db.get_order(order_id)
        if not order or order.get("user_id") != uid:
            await q.answer(t(lang, "not_for_you"), show_alert=True)
            return
        await q.message.reply_text(t(lang, "rating_prompt"), reply_markup=kb.rating_keyboard(order_id))
        return
    if data.startswith("rating:"):
        _, order_id, score = data.split(":")
        order = db.get_order(int(order_id))
        if not order or order.get("user_id") != uid:
            await q.answer(t(lang, "not_for_you"), show_alert=True)
            return
        db.audit_event("order.rated", actor_id=uid, details={"order_id": int(order_id), "score": int(score)})
        await q.edit_message_text(t(lang, "rating_thanks", score=score))
        return
    if data.startswith("support_cat:"):
        category = data.split(":", 1)[1]
        PENDING[uid] = ("support_category", category)
        if category in {"payment", "delivery", "invalid_content", "order"}:
            orders = db.list_user_orders(uid, limit=8)
            await q.message.reply_text(t(lang, "support_choose_order"), reply_markup=kb.support_order_keyboard(lang, orders))
        else:
            PENDING[uid] = ("support", category)
            await q.message.reply_text(t(lang, "support_prompt"))
        return
    if data.startswith("support_order:"):
        order_id = int(data.split(":", 1)[1])
        pending = PENDING.get(uid)
        category = pending[1] if pending and pending[0] == "support_category" else "other"
        PENDING[uid] = ("support_guided", f"{category}|{order_id}")
        await q.message.reply_text(t(lang, "support_prompt"))
        return


# ---------------- Confirmation avant achat ----------------
async def handle_quantity_selection(update, context, lang):
    """Demande au client combien de comptes/produits il veut acheter."""
    q = update.callback_query
    parts = q.data.split(":")
    offer_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 and parts[0] == "qty_page" else 0
    offer = db.get_offer(offer_id)

    if not offer or offer["price"] is None or offer["stock"] <= 0:
        await q.answer(t(lang, "out_of_stock"), show_alert=True)
        return

    if offer["stock"] == 1:
        q.data = f"buyq:{offer_id}:1"
        await handle_buy_confirmation(update, context, lang)
        return

    await q.edit_message_text(
        t(
            lang,
            "choose_quantity",
            offer=offer["name"],
            stock=offer["stock"],
            price=f"{offer['price']:.2f}",
            cur=CURRENCY,
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.quantity_keyboard(lang, offer, page=page),
    )


async def handle_buy_confirmation(update, context, lang):
    """Affiche un r?sum? avant de cr?er la commande."""
    q = update.callback_query
    uid = q.from_user.id
    parts = q.data.split(":")
    offer_id = int(parts[1])
    qty = int(parts[2]) if len(parts) > 2 else 1
    offer = db.get_offer(offer_id)

    if not offer or offer["price"] is None or offer["stock"] <= 0 or qty < 1 or qty > offer["stock"]:
        await q.answer(t(lang, "out_of_stock"), show_alert=True)
        return

    existing = order_service.check_duplicate_pending_order(uid, offer_id)
    if existing:
        await q.edit_message_text(
            t(lang, "duplicate_order", oid=existing["id"],
              offer=existing["offer_name"],
              total=f"{existing['total_price']:.2f}", cur=CURRENCY),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.duplicate_order_keyboard(lang, existing["id"], offer_id, qty),
        )
        return

    svc = db.get_service(offer["service_id"])
    gross_total = round(offer["price"] * qty, 2)
    referral_discount = loyalty_service.discount_for_order(uid, gross_total)
    discount_line = ""
    if referral_discount["amount"] > 0:
        discount_line = t(
            lang,
            "loyalty_discount_line",
            level=(referral_discount["level"] or "").title(),
            percent=referral_discount["discount_percent"],
            amount=f"{referral_discount['amount']:.2f}",
            cur=CURRENCY,
        )
    await q.edit_message_text(
        t(lang, "confirm_purchase",
          emoji=svc["emoji"] if svc else "??",
          service=svc["name"] if svc else "",
          offer=offer["name"],
          price=f"{offer['price']:.2f}",
          cur=CURRENCY,
          qty=qty,
          total=f"{gross_total - referral_discount['amount']:.2f}",
          discount_line=discount_line),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.confirm_buy_keyboard(lang, offer_id, qty),
    )


async def handle_buy_confirmed(update, context, lang, payment_method="binance"):
    """Cr?e la commande apr?s confirmation de l'utilisateur."""
    q = update.callback_query
    uid = q.from_user.id
    parts = q.data.split(":")
    offer_id = int(parts[1])
    qty = int(parts[2]) if len(parts) > 2 else 1
    offer = db.get_offer(offer_id)

    if not offer or offer["price"] is None or offer["stock"] <= 0 or qty < 1 or qty > offer["stock"]:
        await q.answer(t(lang, "out_of_stock"), show_alert=True)
        return

    try:
        order = order_service.create_order(uid, offer, qty=qty, payment_method=payment_method)
    except ValueError as exc:
        await q.answer(str(exc), show_alert=True)
        return

    if order["total_price"] == 0:
        await q.edit_message_text(t(lang, "wallet_payment_processing"), parse_mode=ParseMode.MARKDOWN)
        result = await asyncio.to_thread(payment_service.confirm_wallet_order, order["id"], uid)
        await send_payment_result(q.message, context, lang, order["id"], result, uid)
        return

    text = t(lang, "order_created", oid=order["id"], service=order["service_name"],
             offer=order["offer_name"], qty=order["qty"],
             total=f"{order['total_price']:.2f}", cur=CURRENCY,
             binance_id=BINANCE_PAY_ID, telegram_id=uid)
    await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                              reply_markup=kb.paid_keyboard(lang, order["id"]))
    await run_auto_payment_check(q.message, context, lang, order["id"], uid)


# ---------------- Saisie en attente (txid / admin) ----------------
async def handle_pending_input(update, context, lang):
    uid = update.effective_user.id
    kind, ref = PENDING.get(uid)
    text = update.message.text.strip()

    if kind == "await_txid":
        await process_txid(update, context, lang, ref, text)
        PENDING.pop(uid, None)
        return

    if kind == "await_topup_txid":
        result = await asyncio.to_thread(wallet_service.claim_transfer, uid, text)
        if result["status"] == "confirmed":
            PENDING.pop(uid, None)
            await update.message.reply_text(
                t(lang, "topup_success", amount=f"{result['amount']:.2f}", balance=f"{result['balance']:.2f}"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb.home_keyboard(lang, uid),
            )
        else:
            await update.message.reply_text(
                t(lang, "topup_failed"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb.topup_keyboard(lang),
            )
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

    if uid == ADMIN_ID and kind in {
        "adm_svcname", "adm_svcemoji", "adm_offname", "adm_offnote",
        "adm_offdesc", "adm_offinstructions", "adm_offdelay",
    }:
        if kind not in {"adm_offnote", "adm_offdesc", "adm_offinstructions"} and not text:
            await update.message.reply_text("⚠️ La valeur ne peut pas être vide.")
            return
        if kind == "adm_svcname":
            db.update_service(ref, name=text[:80])
        elif kind == "adm_svcemoji":
            db.update_service(ref, emoji=text[:12])
        elif kind == "adm_offname":
            db.update_offer(ref, name=text[:120])
        elif kind == "adm_offnote":
            db.update_offer(ref, note=text[:250])
        elif kind == "adm_offdesc":
            db.update_offer(ref, description=text[:2000])
        elif kind == "adm_offinstructions":
            offer = db.get_offer(ref)
            description = offer.get("description", "")
            kept = [line for line in description.splitlines() if not line.lower().startswith("instructions:")]
            kept.append(f"Instructions: {text[:1000]}")
            db.update_offer(ref, description="\n".join(kept))
        else:
            db.update_offer(ref, delivery_delay=text[:120])
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
        try:
            items = inventory_service.parse_bulk_inventory(text)
            added = inventory_service.add_items(ref, items)
        except (RuntimeError, ValueError) as exc:
            await update.message.reply_text(f"⚠️ {exc}")
            return
        PENDING.pop(uid, None)
        stock = inventory_service.sync_offer_stock(ref)
        await update.message.reply_text(
            f"✅ {added} compte(s) ajouté(s) et chiffré(s).\n"
            f"♻️ Doublons ignorés : {len(items) - added}\n"
            f"📦 Stock affiché synchronisé : {stock}",
            reply_markup=admin.offer_admin_keyboard(ref),
        )
        return

    if kind == "support":
        ticket = support_service.create_ticket(uid, text, category=str(ref or "other"))
        PENDING[uid] = ("ticket_message", ticket["id"])
        await update.message.reply_text(t(lang, "ticket_created", tid=ticket["id"]))
        await context.bot.send_message(
            ADMIN_ID,
            f"🎫 Nouveau ticket #{ticket['id']}\nUtilisateur: <code>{uid}</code>\n\n{html.escape(text[:2000])}",
            parse_mode=ParseMode.HTML,
        )
        return

    if kind == "support_guided":
        category, order_id_text = str(ref).split("|", 1)
        order_id = int(order_id_text) or None
        if order_id:
            order = db.get_order(order_id)
            if not order or order.get("user_id") != uid:
                await update.message.reply_text(t(lang, "not_for_you"))
                return
        ticket = support_service.create_ticket(uid, text, category=category, order_id=order_id)
        PENDING[uid] = ("ticket_message", ticket["id"])
        await update.message.reply_text(t(lang, "ticket_created", tid=ticket["id"]))
        await context.bot.send_message(
            ADMIN_ID,
            f"🎫 Nouveau ticket #{ticket['id']} ({html.escape(category)})\nUtilisateur: <code>{uid}</code>\n\n{html.escape(text[:2000])}",
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


# ---------------- Traitement de paiement ----------------
async def send_payment_result(message, context, lang, order_id, result, uid):
    if result["status"] in ("delivered", "confirmed", "confirmed_no_delivery"):
        affiliate = result.get("affiliate")
        if affiliate:
            referrer_id = affiliate["referrer_id"]
            ref_lang = lang_of(referrer_id)
            if affiliate["rewarded"]:
                await context.bot.send_message(
                    referrer_id,
                    t(
                        ref_lang,
                        "affiliate_rewarded",
                        count=affiliate["daily_count"],
                        reward=f"{affiliate['reward_amount']:.2f}",
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
        loyalty = result.get("loyalty")
        if loyalty and loyalty.get("activated"):
            await message.reply_text(
                t(
                    lang,
                    "loyalty_activated",
                    level=loyalty["level"].title(),
                    discount=loyalty["discount_percent"],
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        if result["delivered_content"]:
            content = "\n\n".join(result["delivered_content"])
            paid_order = db.get_order(order_id)
            await message.reply_text(
                t(lang, "delivery_received", oid=order_id,
                  service=paid_order["service_name"], offer=paid_order["offer_name"],
                  content=html.escape(content)),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.post_delivery_keyboard(lang, order_id),
            )
        else:
            await message.reply_text(t(lang, "verify_ok", oid=order_id),
                                     parse_mode=ParseMode.MARKDOWN)
            await admin.notify_new_order(context, db.get_order(order_id))
    elif result["status"] == "already_paid":
        await message.reply_text(t(lang, "already_paid", oid=order_id),
                                 parse_mode=ParseMode.MARKDOWN)
    else:
        error_code = result.get("error_code", "unknown")
        if error_code == "too_short":
            await message.reply_text(t(lang, "txid_too_short"))
            PENDING[uid] = ("await_txid", order_id)
            return
        error_key = {
            "wrong_amount": "payment_wrong_amount",
            "wrong_currency": "payment_wrong_currency",
            "wrong_memo": "payment_wrong_memo",
            "not_found": "payment_not_found",
            "already_used": "payment_txid_used",
        }.get(error_code, "verify_failed")
        await message.reply_text(t(lang, error_key, oid=order_id),
                                 parse_mode=ParseMode.MARKDOWN)
        PENDING[uid] = ("await_txid", order_id)


def payment_scanner_frame(step: int, width: int = 9) -> str:
    """Build a looping neon scanner; it represents activity, not fake progress."""
    cycle = list(range(width)) + list(range(width - 2, 0, -1))
    position = cycle[step % len(cycle)]
    cells = ["⬛"] * width
    cells[position] = "💠"
    if position > 0:
        cells[position - 1] = "🟦"
    if position < width - 1:
        cells[position + 1] = "🟪"
    return "".join(cells)


async def run_auto_payment_check(message, context, lang, order_id, uid):
    scanner = await message.reply_text(
        t(lang, "payment_scanner", frame=payment_scanner_frame(0), oid=order_id),
        parse_mode=ParseMode.MARKDOWN,
    )
    deadline = asyncio.get_running_loop().time() + 120
    step = 0
    while asyncio.get_running_loop().time() < deadline:
        result = await asyncio.to_thread(payment_service.auto_check_payment, order_id, uid)
        if result["status"] in ("delivered", "confirmed", "confirmed_no_delivery", "already_paid"):
            with contextlib.suppress(Exception):
                await scanner.edit_text(t(lang, "payment_scanner_success", oid=order_id), parse_mode=ParseMode.MARKDOWN)
            await send_payment_result(message, context, lang, order_id, result, uid)
            return
        step += 1
        with contextlib.suppress(Exception):
            await scanner.edit_text(
                t(lang, "payment_scanner", frame=payment_scanner_frame(step), oid=order_id),
                parse_mode=ParseMode.MARKDOWN,
            )
        await asyncio.sleep(2)
    with contextlib.suppress(Exception):
        await scanner.edit_text(t(lang, "payment_scanner_timeout", oid=order_id), parse_mode=ParseMode.MARKDOWN)
    PENDING[uid] = ("await_txid", order_id)
    await message.reply_text(t(lang, "auto_check_timeout", oid=order_id), parse_mode=ParseMode.MARKDOWN)


async def process_txid(update, context, lang, order_id, txid):
    uid = update.effective_user.id
    await update.message.reply_text(t(lang, "verifying"))
    result = await asyncio.to_thread(
        payment_service.submit_payment, order_id, txid, uid
    )
    await send_payment_result(update.message, context, lang, order_id, result, uid)

# ---------------- Mes commandes ----------------
async def show_my_orders(update, context, lang):
    uid = update.effective_user.id
    orders = db.list_user_orders(uid, limit=500)
    if not orders:
        await update.effective_message.reply_text(t(lang, "no_orders"), reply_markup=kb.orders_keyboard(lang))
        return

    groups = order_service_groups(orders)
    await update.effective_message.reply_text(
        t(lang, "orders_choose_service"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.orders_services_keyboard(lang, groups, len(orders)),
    )


def order_service_groups(orders):
    service_emojis = {service["name"]: service.get("emoji", "📦") for service in db.list_services()}
    grouped = {}
    for order in orders:
        name = str(order.get("service_name") or "Other")
        grouped.setdefault(name, {
            "name": name,
            "emoji": service_emojis.get(name, "📦"),
            "orders": [],
        })["orders"].append(order)
    groups = sorted(grouped.values(), key=lambda group: (-len(group["orders"]), group["name"].lower()))
    for group in groups:
        group["count"] = len(group["orders"])
    return groups


def orders_text_export(lang, orders, title):
    lines = [title, "=" * max(24, len(title)), ""]
    for order in orders:
        created_at = order.get("created_at")
        date = datetime.fromtimestamp(created_at, UTC).strftime("%Y-%m-%d %H:%M UTC") if created_at else "—"
        lines.extend([
            f"Order #{order['id']}",
            f"Service: {order.get('service_name') or '—'}",
            f"Offer: {order.get('offer_name') or '—'}",
            f"Quantity: {order.get('qty', 1)}",
            f"Total: {float(order.get('total_price') or 0):.2f} {order.get('currency', CURRENCY)}",
            f"Status: {status_label(lang, order.get('status', ''))}",
            f"Date: {date}",
            "-" * 32,
        ])
    return "\n".join(lines)


async def send_orders_export(query, lang, orders, title):
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", title).strip("-").lower() or "orders"
    content = orders_text_export(lang, orders, title).encode("utf-8")
    await query.message.reply_document(
        document=InputFile(io.BytesIO(content), filename=f"{safe_name}.txt"),
        caption=t(lang, "orders_file_caption", service=title, count=len(orders)),
        reply_markup=kb.orders_keyboard(lang),
    )


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
        await show_callback_screen(
            q,
            "🛠️ *Panneau Admin*",
            reply_markup=admin.admin_panel_keyboard(),
        )
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
            "🔐 *Import massif sécurisé*\n\n"
            "Chaque ligne commençant par `#` ouvre un nouveau compte.\n"
            "Toutes les lignes suivantes appartiennent à ce compte jusqu'au prochain `#`.\n\n"
            "Exemple :\n"
            "`#1`\n"
            "`Email: client1@example.com`\n"
            "`Password: secret1`\n"
            "`Instructions: profil A`\n\n"
            "`#2`\n"
            "`Email: client2@example.com`\n"
            "`Password: secret2`\n\n"
            f"Actuellement disponibles : {stats['available']}",
            parse_mode=ParseMode.MARKDOWN,
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
    if data.startswith(("adm_offname:", "adm_offnote:", "adm_offdesc:", "adm_offinstructions:", "adm_offdelay:")):
        action, oid = data.split(":")
        PENDING[uid] = (action, int(oid))
        prompts = {
            "adm_offname": "✏️ Envoyez le nouveau nom :",
            "adm_offnote": "📝 Envoyez la nouvelle note/garantie :",
            "adm_offdesc": "📄 Envoyez la description complète :",
            "adm_offinstructions": "📌 Envoyez les instructions destinées au client :",
            "adm_offdelay": "🚚 Envoyez le délai de livraison affiché :",
        }
        await q.message.reply_text(prompts[action])
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
    issues = configuration_issues()
    if issues:
        raise RuntimeError(f"Configuration incomplète : {', '.join(issues)}")
    db.init_db()
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    # Groupe -2 : blocage des utilisateurs bannis avant les handlers du groupe 0.
    app.add_handler(MessageHandler(filters.ALL, block_banned_users), group=-2)
    app.add_handler(CallbackQueryHandler(block_banned_users), group=-2)
    app.add_handler(
        CallbackQueryHandler(
            block_maintenance_purchases,
            pattern=r"^(buy|buyq|qty_page|confirm_buy|pay_wallet|pay_binance):",
        ),
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
