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

from telegram import ForceReply, InputFile, LinkPreviewOptions, Update
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
    BINANCE_PAY_ID,
    BOT_TOKEN,
    CURRENCY,
    DEFAULT_LANG,
    SHOP_NAME,
    configuration_issues,
)
from i18n import TRANSLATIONS, status_label, t

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
# "await_txid": order_id  |  "adm_setprice": offer_id
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
AUTO_PAYMENT_TASKS = {}
AUTO_PAYMENT_MESSAGES = {}


async def stop_auto_payment_check(order_id):
    """Cancel a running scanner and remove its waiting message."""
    task = AUTO_PAYMENT_TASKS.pop(int(order_id), None)
    if task and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    scanner = AUTO_PAYMENT_MESSAGES.pop(int(order_id), None)
    if scanner:
        with contextlib.suppress(Exception):
            await scanner.delete()


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





def numbered_delivery_content(items):
    """Format delivered inventory items as a clearly numbered account list."""
    return "\n\n".join(
        f"#{index}\n{str(item).strip()}"
        for index, item in enumerate(items or [], start=1)
        if str(item).strip()
    )

def lang_of(user_id):
    return db.get_user_lang(user_id) or DEFAULT_LANG


async def notify_successful_referral(context, referrer_id):
    """Notify the referrer after every valid referral and each 10-member reward."""
    stats = affiliate_service.get_stats(referrer_id)
    lang = lang_of(referrer_id)
    if stats["referrals"] and stats["referrals"] % 10 == 0:
        key = "affiliate_ten_success"
        values = {"balance": f"{stats['balance_cents'] / 100:.2f}"}
    else:
        key = "affiliate_referral_success"
        values = {
            "progress": stats["progress"],
            "remaining": stats["remaining"],
        }
    await context.bot.send_message(
        referrer_id,
        premium_customer_text(lang, key, **values),
        parse_mode=ParseMode.HTML,
    )


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


def compact_offer_text(offer: dict, lang: str) -> str:
    """Build the compact public offer card used with or without an image."""
    labels = {
        "fr": ("PRIX", "STOCK", "VENDUS", "GARANTIE", "DESCRIPTION"),
        "en": ("PRICE", "STOCK", "SOLD", "WARRANTY", "DESCRIPTION"),
        "ar": ("السعر", "المخزون", "تم البيع", "الضمان", "الوصف"),
    }
    price_label, stock_label, sold_label, warranty_label, description_label = labels.get(lang, labels["en"])
    description = (offer.get("description") or "").strip() or "—"
    warranty = offer.get("note") or "—"
    price = "—" if offer.get("price") is None else f"{offer['price']:.2f}"
    sold = db.offer_sold_count(offer["id"])
    return (
        f"🏷 <b>{html.escape(offer['name'])}</b>\n\n"
        f"💎 <b>{price_label}:</b> {price} {html.escape(offer.get('currency', CURRENCY))}\n"
        f"📦 <b>{stock_label}:</b> {int(offer.get('stock') or 0)}\n"
        f"🛒 <b>{sold_label}:</b> {sold}\n"
        f"🛡 <b>{warranty_label}:</b> {html.escape(warranty[:120])}\n\n"
        f"💬 <b>{description_label}:</b>\n{render_stored_rich_text(description, parse_legacy_markdown=False)}"
    )


def admin_text_preview(key: str) -> str:
    current = db.get_text_override(key, "en") or TRANSLATIONS.get(key, {}).get("en") or "—"
    return (
        f"✏️ <b>{html.escape(key)}</b>\n\n"
        f"🇬🇧 <b>English</b>\n<pre>{html.escape(current[:2700])}</pre>\n"
        "Choose the text to edit or use the arrows:"
    )


def custom_emojis_from_message(message):
    """Extract every unique Premium custom emoji from text or caption entities."""
    found = []
    entities = list(getattr(message, "entities", None) or [])
    entities.extend(getattr(message, "caption_entities", None) or [])
    for entity in entities:
        entity_type = getattr(getattr(entity, "type", None), "value", getattr(entity, "type", None))
        emoji_id = getattr(entity, "custom_emoji_id", None)
        if str(entity_type) == "custom_emoji" and emoji_id and emoji_id not in found:
            found.append(emoji_id)
    return found


def custom_emoji_from_message(message):
    """Return the first Premium emoji, the only one Telegram allows as a button icon."""
    emojis = custom_emojis_from_message(message)
    return emojis[0] if emojis else ""


def text_without_custom_emojis(message):
    """Remove Premium emoji placeholders using Telegram's UTF-16 entity offsets."""
    value = (getattr(message, "text", None) or getattr(message, "caption", None) or "")
    entities = list(getattr(message, "entities", None) or [])
    entities.extend(getattr(message, "caption_entities", None) or [])
    encoded = bytearray(value.encode("utf-16-le"))
    ranges = []
    for entity in entities:
        entity_type = getattr(getattr(entity, "type", None), "value", getattr(entity, "type", None))
        if str(entity_type) == "custom_emoji":
            ranges.append((int(entity.offset) * 2, (int(entity.offset) + int(entity.length)) * 2))
    for start, end in sorted(ranges, reverse=True):
        del encoded[start:end]
    return encoded.decode("utf-16-le").strip()


def text_with_custom_emoji_tokens(message):
    """Preserve every Premium emoji ID and its exact UTF-16 text position."""
    value = (getattr(message, "text", None) or getattr(message, "caption", None) or "")
    entities = list(
        (getattr(message, "entities", None) if getattr(message, "text", None) else
         getattr(message, "caption_entities", None)) or []
    )
    encoded = bytearray(value.encode("utf-16-le"))
    replacements = []
    for entity in entities:
        entity_type = getattr(getattr(entity, "type", None), "value", getattr(entity, "type", None))
        emoji_id = getattr(entity, "custom_emoji_id", None)
        if str(entity_type) != "custom_emoji" or not emoji_id:
            continue
        start = int(entity.offset) * 2
        end = (int(entity.offset) + int(entity.length)) * 2
        fallback = bytes(encoded[start:end]).decode("utf-16-le")
        token = f"[[TGEMOJI:{emoji_id}:{fallback.encode('utf-8').hex()}]]"
        replacements.append((start, end, token.encode("utf-16-le")))
    for start, end, token in sorted(replacements, reverse=True):
        encoded[start:end] = token
    return encoded.decode("utf-16-le").strip()


def rich_text_from_message(message):
    """Capture Telegram's exact entity-aware HTML from an admin message."""
    html_value = (
        getattr(message, "text_html", None)
        or getattr(message, "caption_html", None)
    )
    if html_value:
        return f"[[HTML]]{html_value}"
    return text_with_custom_emoji_tokens(message)


def render_stored_rich_text(value, *, parse_legacy_markdown=True):
    """Render trusted admin HTML or legacy Markdown/token text as Telegram HTML."""
    raw_value = str(value or "")
    if raw_value.startswith("[[HTML]]"):
        return raw_value.removeprefix("[[HTML]]")
    rendered = html.escape(raw_value)
    if parse_legacy_markdown:
        rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
        rendered = re.sub(r"\*([^*]+)\*", r"<b>\1</b>", rendered)
        rendered = re.sub(r"_([^_]+)_", r"<i>\1</i>", rendered)

    def render_custom_emoji(match):
        emoji_id, fallback_hex = match.groups()
        with contextlib.suppress(ValueError, UnicodeDecodeError):
            fallback = bytes.fromhex(fallback_hex).decode("utf-8")
            return f'<tg-emoji emoji-id="{emoji_id}">{html.escape(fallback)}</tg-emoji>'
        return ""

    return re.sub(
        r"\[\[TGEMOJI:([0-9A-Za-z_-]+):([0-9a-fA-F]+)\]\]",
        render_custom_emoji,
        rendered,
    )


# ---------------- /start ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    is_new = db.upsert_user(u.id, u.username or "", u.first_name or "")
    if is_new and context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0][4:])
            accepted = affiliate_service.register_referral_link(u.id, referrer_id)
            if accepted:
                with contextlib.suppress(Exception):
                    await notify_successful_referral(context, referrer_id)
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
        qualified=stats["valid_referrals"], total_buy=f"{account['total_paid']:.2f}",
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
        referrals=stats["referrals"], progress=stats["progress"],
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
    if lang != "en":
        await q.answer("English is the only available language.", show_alert=True)
        return
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
        "await_quantity",
        "adm_setprice",
        "adm_svcname",
        "adm_svcemoji",
        "adm_offname",
        "adm_offemoji",
        "adm_offnote",
        "adm_offdesc",
        "adm_offdelay",
        "adm_addsvc",
        "adm_addoff",
        "adm_addoff_image",
        "adm_addoff_name",
        "adm_addoff_warranty",
        "adm_addoff_description",
        "adm_addoff_price",
        "adm_offimage",
        "adm_text_override",
        "adm_btn_add",
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
            await show_callback_screen(
                q, t(lang, "no_offers"), reply_markup=kb.services_keyboard(lang),
            )
            return
        await show_callback_screen(
            q,
            t(lang, "service_title", emoji=svc["emoji"], name=svc["name"]),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.offers_keyboard(lang, sid),
        )
        return
    if data.startswith("off:"):
        oid = int(data.split(":")[1])
        off = db.get_offer(oid)
        if not off or int(off.get("stock") or 0) <= 0:
            await q.message.reply_text(
                premium_customer_text(lang, "out_of_stock"),
                parse_mode=ParseMode.HTML,
            )
            return
        svc = db.get_service(off["service_id"])
        detail_text = compact_offer_text(off, lang)
        photo_file_id = off.get("photo_file_id")
        if photo_file_id:
            if len(detail_text) <= 900:
                await q.message.reply_photo(
                    photo=photo_file_id,
                    caption=detail_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb.offer_detail_keyboard(lang, off),
                )
            else:
                await q.message.reply_photo(photo=photo_file_id)
                await q.message.reply_text(
                    detail_text,
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                    reply_markup=kb.offer_detail_keyboard(lang, off),
                )
            with contextlib.suppress(Exception):
                await q.message.delete()
            return
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
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=kb.offer_detail_keyboard(lang, off),
            )
            with contextlib.suppress(Exception):
                await q.message.delete()
            return
        await q.edit_message_text(
            detail_text,
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
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
        await stop_auto_payment_check(order_id)
        order = db.get_order(order_id)
        if order and order.get("user_id") == uid:
            order_service.cancel_order(order_id, reason="Cancelled by customer")
        await q.edit_message_text(
            premium_customer_text(lang, "cancelled_msg"),
            parse_mode=ParseMode.HTML,
        )
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
        await stop_auto_payment_check(oid)
        PENDING[uid] = ("await_txid", oid)
        await q.message.reply_text(t(lang, "ask_txid", oid=oid),
                                   parse_mode=ParseMode.MARKDOWN)
        return
    if data.startswith("verify_auto:"):
        oid = int(data.split(":", 1)[1])
        order = db.get_order(oid)
        if not order or order.get("user_id") != uid:
            await q.answer(t(lang, "not_for_you"), show_alert=True)
            return
        await stop_auto_payment_check(oid)
        task = context.application.create_task(
            run_auto_payment_check(q.message, context, lang, oid, uid),
            update=update,
            name=f"payment-scan-{oid}",
        )
        AUTO_PAYMENT_TASKS[oid] = task

        def cleanup_scan(completed_task, order_id=oid):
            if AUTO_PAYMENT_TASKS.get(order_id) is completed_task:
                AUTO_PAYMENT_TASKS.pop(order_id, None)
                AUTO_PAYMENT_MESSAGES.pop(order_id, None)

        task.add_done_callback(cleanup_scan)
        return
    if data.startswith("continue_pay:"):
        oid = int(data.split(":")[1])
        order = db.get_order(oid)
        if order and order["user_id"] == uid:
            text = premium_customer_text(
                lang, "order_created", oid=oid, service=order["service_name"],
                offer=order["offer_name"], qty=order["qty"],
                total=f"{order['total_price']:.2f}", cur=CURRENCY,
                binance_id=BINANCE_PAY_ID, telegram_id=uid,
            )
            await q.message.reply_text(
                text, parse_mode=ParseMode.HTML,
                reply_markup=kb.paid_keyboard(
                    lang, oid, BINANCE_PAY_ID, f"{order['total_price']:.2f}", CURRENCY,
                ),
            )
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
    offer = db.get_offer(offer_id)

    if not offer or offer["price"] is None or offer["stock"] <= 0:
        await q.answer(t(lang, "out_of_stock"), show_alert=True)
        return

    PENDING[q.from_user.id] = ("await_quantity", offer_id)
    send_quantity_prompt = q.message.reply_text if q.message.photo else q.edit_message_text
    await send_quantity_prompt(
        t(
            lang,
            "choose_quantity",
            offer=offer["name"],
            stock=offer["stock"],
            price=f"{offer['price']:.2f}",
            cur=CURRENCY,
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


async def send_buy_confirmation(send, uid, offer_id, qty, lang):
    """Validate a typed quantity and display the purchase summary."""
    offer = db.get_offer(offer_id)
    if not offer or offer["price"] is None or offer["stock"] <= 0 or qty < 1 or qty > offer["stock"]:
        return False
    svc = db.get_service(offer["service_id"])
    gross_total = round(offer["price"] * qty, 2)
    referral_discount = loyalty_service.discount_for_order(uid, gross_total)
    discount_line = ""
    if referral_discount["amount"] > 0:
        discount_line = t(
            lang, "loyalty_discount_line",
            level=(referral_discount["level"] or "").title(),
            percent=referral_discount["discount_percent"],
            amount=f"{referral_discount['amount']:.2f}", cur=CURRENCY,
        )
    await send(
        t(lang, "confirm_purchase",
          emoji=svc["emoji"] if svc else "📦", service=svc["name"] if svc else "",
          offer=offer["name"], price=f"{offer['price']:.2f}", cur=CURRENCY, qty=qty,
          total=f"{gross_total - referral_discount['amount']:.2f}", discount_line=discount_line),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.confirm_buy_keyboard(lang, offer_id, qty),
    )
    return True


async def handle_buy_confirmation(update, context, lang):
    """Affiche un r?sum? avant de cr?er la commande."""
    q = update.callback_query
    uid = q.from_user.id
    parts = q.data.split(":")
    offer_id = int(parts[1])
    qty = int(parts[2]) if len(parts) > 2 else 1
    if not await send_buy_confirmation(q.edit_message_text, uid, offer_id, qty, lang):
        await q.answer(t(lang, "out_of_stock"), show_alert=True)


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
        order_service.cancel_incomplete_orders(uid, exclude_order_id=order["id"])
    except ValueError as exc:
        await q.answer(str(exc), show_alert=True)
        return

    if order["total_price"] == 0:
        await q.edit_message_text(t(lang, "wallet_payment_processing"), parse_mode=ParseMode.MARKDOWN)
        result = await asyncio.to_thread(payment_service.confirm_wallet_order, order["id"], uid)
        await send_payment_result(q.message, context, lang, order["id"], result, uid)
        return

    text = premium_customer_text(
        lang, "order_created", oid=order["id"], service=order["service_name"],
        offer=order["offer_name"], qty=order["qty"],
        total=f"{order['total_price']:.2f}", cur=CURRENCY,
        binance_id=BINANCE_PAY_ID, telegram_id=uid,
    )
    await q.edit_message_text(text, parse_mode=ParseMode.HTML,
                              reply_markup=kb.paid_keyboard(
                                  lang, order["id"], BINANCE_PAY_ID,
                                  f"{order['total_price']:.2f}", CURRENCY,
                              ))


# ---------------- Saisie en attente (txid / admin) ----------------
async def handle_pending_input(update, context, lang):
    uid = update.effective_user.id
    kind, ref = PENDING.get(uid)
    text = update.message.text.strip()

    if kind == "await_quantity":
        offer = db.get_offer(int(ref))
        try:
            qty = int(text)
        except ValueError:
            qty = 0
        stock = int((offer or {}).get("stock") or 0)
        if qty < 1 or qty > stock:
            await update.message.reply_text(
                t(lang, "quantity_invalid", stock=stock),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        PENDING.pop(uid, None)
        await send_buy_confirmation(update.message.reply_text, uid, int(ref), qty, lang)
        return

    if kind == "adm_text_override" and uid == ADMIN_ID:
        saved_key = ""
        override_icon = custom_emoji_from_message(update.message)
        override_text = rich_text_from_message(update.message)
        if isinstance(ref, str) and "|" in ref:
            key, selected_lang = ref.rsplit("|", 1)
            if key not in TRANSLATIONS or selected_lang not in {"fr", "en", "ar"}:
                await update.message.reply_text("⚠️ Sélection de texte invalide.")
                return
            db.set_text_override(key, selected_lang, override_text, override_icon)
            saved_key = key
        else:
            parts = [part.strip() for part in text.split("|", 2)]
            if len(parts) != 3 or parts[1] not in {"fr", "en", "ar"} or not parts[0] or not parts[2]:
                await update.message.reply_text("⚠️ Format : `clé | fr/en/ar | nouveau texte`", parse_mode=ParseMode.MARKDOWN)
                return
            db.set_text_override(parts[0], parts[1], parts[2])
            saved_key = parts[0]
        PENDING.pop(uid, None)
        keys = sorted(TRANSLATIONS)
        if saved_key in keys:
            category = admin.text_category_for_key(saved_key)
            await update.message.reply_text(
                "✅ Texte enregistré immédiatement. Choisissez un autre texte à modifier :",
                reply_markup=admin.texts_category_keyboard(category),
            )
        else:
            await update.message.reply_text("✅ Texte enregistré immédiatement.", reply_markup=admin.customize_keyboard())
        return

    if kind == "adm_btn_add" and uid == ADMIN_ID:
        parts = [part.strip() for part in text.split("|", 3)]
        if len(parts) != 4 or not re.fullmatch(r"https?://\S+", parts[3]):
            await update.message.reply_text(
                "⚠️ Format : `Français | English | العربية | https://exemple.com`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        db.add_custom_button(*parts)
        PENDING.pop(uid, None)
        await update.message.reply_text("✅ Bouton ajouté au menu principal.", reply_markup=admin.buttons_editor_keyboard())
        return

    if kind == "adm_addoff_image" and uid == ADMIN_ID:
        await update.message.reply_text("🖼 Envoyez une image (photo), pas un message texte.")
        return

    if kind == "adm_offimage" and uid == ADMIN_ID:
        await update.message.reply_text("🖼 Envoyez la nouvelle image comme photo Telegram.")
        return

    if kind == "adm_addoff_name" and uid == ADMIN_ID:
        clean_name = kb.clean_button_name(text)[:120]
        if not clean_name:
            await update.message.reply_text("⚠️ Le nom de l’offre ne peut pas être vide.")
            return
        data = dict(ref)
        data["name"] = clean_name
        PENDING[uid] = ("adm_addoff_warranty", data)
        await update.message.reply_text(
            "🛡 *Étape 3/5* — envoyez la garantie de l’offre (exemple : 30 jours) :",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if kind == "adm_addoff_warranty" and uid == ADMIN_ID:
        warranty = text[:250].strip()
        if not warranty:
            await update.message.reply_text("⚠️ La garantie ne peut pas être vide.")
            return
        data = dict(ref)
        data["warranty"] = warranty
        PENDING[uid] = ("adm_addoff_description", data)
        await update.message.reply_text(
            "📝 *Étape 4/5* — envoyez la description de l’offre :",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if kind == "adm_addoff_description" and uid == ADMIN_ID:
        description = rich_text_from_message(update.message)
        if not description:
            await update.message.reply_text("⚠️ La description ne peut pas être vide.")
            return
        data = dict(ref)
        data["description"] = description
        PENDING[uid] = ("adm_addoff_price", data)
        await update.message.reply_text(
            "💵 *Étape 5/5* — envoyez le prix unitaire en USDT (exemple : 4.99) :",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if kind == "adm_addoff_price" and uid == ADMIN_ID:
        try:
            price = float(text.replace(",", "."))
            if price < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Prix invalide. Envoyez un nombre, par exemple : 4.99")
            return
        data = dict(ref)
        offer_id = db.add_offer(
            data["service_id"], data["name"], price, 0,
            note=data["warranty"],
            description=data["description"],
            instructions="",
            photo_file_id=data["photo_file_id"],
        )
        PENDING.pop(uid, None)
        await update.message.reply_text(
            "✅ Offre créée.\n\n"
            "📦 Le stock sera calculé automatiquement à partir des comptes ajoutés.\n"
            "🛒 Les ventes seront calculées automatiquement à partir des commandes confirmées.\n\n"
            "Ajoutez maintenant les comptes pour alimenter le stock.",
            reply_markup=admin.offer_admin_keyboard(offer_id),
        )
        return

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

    if uid == ADMIN_ID and kind in {
        "adm_svcname", "adm_svcemoji", "adm_offname", "adm_offemoji", "adm_offnote",
        "adm_offdesc", "adm_offdelay",
    }:
        if kind not in {"adm_offnote", "adm_offdesc"} and not text:
            await update.message.reply_text("⚠️ La valeur ne peut pas être vide.")
            return
        if kind == "adm_svcname":
            service = db.get_service(ref)
            clean_name = kb.clean_button_name(text)
            db.update_service(
                ref,
                name=(clean_name[:80] or service["name"]),
                custom_emoji_id=custom_emoji_from_message(update.message),
            )
        elif kind == "adm_svcemoji":
            custom_emoji_id = custom_emoji_from_message(update.message)
            db.update_service(
                ref,
                emoji="" if custom_emoji_id else text[:12],
                custom_emoji_id=custom_emoji_id,
            )
        elif kind == "adm_offname":
            offer = db.get_offer(ref)
            clean_name = kb.clean_button_name(text)
            db.update_offer(
                ref,
                name=(clean_name[:120] or offer["name"]),
                custom_emoji_id=custom_emoji_from_message(update.message),
            )
        elif kind == "adm_offemoji":
            db.update_offer(ref, custom_emoji_id=custom_emoji_from_message(update.message))
        elif kind == "adm_offnote":
            db.update_offer(ref, note=text[:250])
        elif kind == "adm_offdesc":
            db.update_offer(ref, description=rich_text_from_message(update.message))
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
        db.add_service(
            kb.clean_button_name(name)[:80],
            "" if custom_emoji_from_message(update.message) else emoji[:12],
            custom_emoji_id=custom_emoji_from_message(update.message),
        )
        PENDING.pop(uid, None)
        await update.message.reply_text("✅ Service ajouté.", reply_markup=admin.admin_panel_keyboard())
        return

    if kind == "adm_addoff" and uid == ADMIN_ID:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 2:
            await update.message.reply_text("⚠️ Format : Nom | prix | note optionnelle")
            return
        try:
            price = float(parts[1].replace(",", "."))
            if price < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Prix invalide.")
            return
        note = parts[2][:250] if len(parts) > 2 else ""
        db.add_offer(
            ref,
            kb.clean_button_name(parts[0])[:120],
            price,
            0,
            note,
            custom_emoji_id=custom_emoji_from_message(update.message),
        )
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
                    premium_customer_text(
                        ref_lang,
                        "affiliate_rewarded",
                        count=affiliate["daily_count"],
                        reward=f"{affiliate['reward_amount']:.2f}",
                    ),
                    parse_mode=ParseMode.HTML,
                )
        loyalty = result.get("loyalty")
        if loyalty and loyalty.get("activated"):
            await message.reply_text(
                premium_customer_text(
                    lang,
                    "loyalty_activated",
                    level=loyalty["level"].title(),
                    discount=loyalty["discount_percent"],
                ),
                parse_mode=ParseMode.HTML,
            )
        if result["delivered_content"]:
            content = numbered_delivery_content(result["delivered_content"])
            paid_order = db.get_order(order_id)
            await message.reply_text(
                premium_customer_text(lang, "delivery_received", oid=order_id,
                  service=paid_order["service_name"], offer=paid_order["offer_name"],
                  content=content),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.post_delivery_keyboard(lang, order_id),
            )
        else:
            await message.reply_text(premium_customer_text(lang, "verify_ok", oid=order_id),
                                     parse_mode=ParseMode.HTML)
            await admin.notify_new_order(context, db.get_order(order_id))
    elif result["status"] == "already_paid":
        await message.reply_text(premium_customer_text(lang, "already_paid", oid=order_id),
                                 parse_mode=ParseMode.HTML)
    else:
        error_code = result.get("error_code", "unknown")
        if error_code == "too_short":
            await message.reply_text(
                premium_customer_text(lang, "txid_too_short"),
                parse_mode=ParseMode.HTML,
            )
            PENDING[uid] = ("await_txid", order_id)
            return
        error_key = {
            "wrong_amount": "payment_wrong_amount",
            "wrong_currency": "payment_wrong_currency",
            "wrong_memo": "payment_wrong_memo",
            "not_found": "payment_not_found",
            "already_used": "payment_txid_used",
        }.get(error_code, "verify_failed")
        await message.reply_text(premium_customer_text(lang, error_key, oid=order_id),
                                 parse_mode=ParseMode.HTML)
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
        premium_customer_text(lang, "payment_scanner", frame=payment_scanner_frame(0), oid=order_id),
        parse_mode=ParseMode.HTML,
        reply_markup=kb.txid_verify_keyboard(lang, order_id),
    )
    deadline = asyncio.get_running_loop().time() + 120
    step = 0
    while asyncio.get_running_loop().time() < deadline:
        current_order = db.get_order(order_id)
        if not current_order or current_order.get("status") in {"cancelled", "expired", "refunded"}:
            with contextlib.suppress(Exception):
                await scanner.delete()
            return
        result = await asyncio.to_thread(payment_service.auto_check_payment, order_id, uid)
        if result["status"] in ("delivered", "confirmed", "confirmed_no_delivery", "already_paid"):
            with contextlib.suppress(Exception):
                await scanner.edit_text(
                    premium_customer_text(lang, "payment_scanner_success", oid=order_id),
                    parse_mode=ParseMode.HTML,
                )
            await send_payment_result(message, context, lang, order_id, result, uid)
            return
        step += 1
        with contextlib.suppress(Exception):
            await scanner.edit_text(
                premium_customer_text(lang, "payment_scanner", frame=payment_scanner_frame(step), oid=order_id),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.txid_verify_keyboard(lang, order_id),
            )
        await asyncio.sleep(2)
    with contextlib.suppress(Exception):
        await scanner.edit_text(
            premium_customer_text(lang, "payment_scanner_timeout", oid=order_id),
            parse_mode=ParseMode.HTML,
            reply_markup=kb.txid_verify_keyboard(lang, order_id),
        )
    await message.reply_text(
        premium_customer_text(lang, "auto_check_timeout", oid=order_id),
        parse_mode=ParseMode.HTML,
        reply_markup=kb.txid_verify_keyboard(lang, order_id),
    )
    AUTO_PAYMENT_MESSAGES[order_id] = scanner


def premium_customer_text(lang: str, key: str, **kwargs) -> str:
    """Render selected customer texts as HTML with their Premium emoji."""
    raw_override = db.get_text_override(key, lang)
    if raw_override is not None and str(raw_override).strip():
        raw_value = str(raw_override)
        if kwargs:
            format_kwargs = kwargs
            if raw_value.startswith("[[HTML]]"):
                format_kwargs = {name: html.escape(str(value)) for name, value in kwargs.items()}
                if key == "order_created":
                    for name in ("total", "binance_id", "telegram_id"):
                        if name in format_kwargs:
                            format_kwargs[name] = f"<code>{format_kwargs[name]}</code>"
            with contextlib.suppress(KeyError, IndexError, ValueError):
                raw_value = raw_value.format(**format_kwargs)
    else:
        raw_value = t(lang, key, **kwargs)
    if key == "order_created" and not raw_value.startswith("[[HTML]]"):
        # Keep the three payment values individually copyable in Telegram,
        # even when the admin's customized template uses plain placeholders.
        copyable_values = {
            name: str(kwargs[name])
            for name in ("total", "binance_id", "telegram_id")
            if name in kwargs
        }
        if copyable_values:
            raw_template = str(raw_override) if raw_override is not None else ""
            for name, plain_value in copyable_values.items():
                if f"`{{{name}}}`" not in raw_template:
                    raw_value = raw_value.replace(plain_value, f"`{plain_value}`", 1)
    value = render_stored_rich_text(raw_value)
    inline_emojis = "<tg-emoji " in value
    emoji_id = db.get_text_override_icon(key, lang)
    if emoji_id and not inline_emojis:
        value = f'<tg-emoji emoji-id="{html.escape(emoji_id)}">⭐</tg-emoji> {value}'
    return value


async def process_txid(update, context, lang, order_id, txid):
    uid = update.effective_user.id
    await update.message.reply_text(
        premium_customer_text(lang, "verifying"),
        parse_mode=ParseMode.HTML,
    )
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


async def handle_pending_photo(update, context):
    """Capture the advertising image during the guided offer creation flow."""
    uid = update.effective_user.id
    pending = PENDING.get(uid)
    if uid != ADMIN_ID or not pending or pending[0] not in {"adm_addoff_image", "adm_offimage"}:
        return
    if pending[0] == "adm_offimage":
        offer_id = int(pending[1])
        db.update_offer(offer_id, photo_file_id=update.message.photo[-1].file_id)
        PENDING.pop(uid, None)
        await update.message.reply_text(
            "✅ Image publicitaire mise à jour. Elle sera affichée lorsque le client ouvrira l’offre.",
            reply_markup=admin.offer_admin_keyboard(offer_id),
        )
        return
    service_id = pending[1]
    photo_file_id = update.message.photo[-1].file_id
    PENDING[uid] = ("adm_addoff_name", {
        "service_id": service_id,
        "photo_file_id": photo_file_id,
    })
    await update.message.reply_text(
        "✏️ *Nouvelle offre — étape 2/6*\n\nEnvoyez le nom de l’offre :",
        parse_mode=ParseMode.MARKDOWN,
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

    if data == "adm_customize":
        await q.edit_message_text(
            "🎛 *Personnalisation du bot*\n\nModifiez les textes, la visibilité des boutons et les liens personnalisés.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin.customize_keyboard(),
        )
        return
    if data == "adm_texts":
        await q.edit_message_text(
            "🗂 *Textes du bot par catégorie*\n\nChoisissez la partie du bot que vous souhaitez modifier :",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin.text_categories_keyboard(),
        )
        return
    if data.startswith("adm_text_cat:"):
        category, page = data.removeprefix("adm_text_cat:").rsplit(":", 1)
        labels = dict(admin.TEXT_CATEGORIES)
        await q.edit_message_text(
            f"{labels.get(category, '📝 Textes')}\n\nChoisissez un texte à modifier :",
            reply_markup=admin.texts_category_keyboard(category, int(page)),
        )
        return
    if data.startswith("adm_text_page:"):
        page = int(data.split(":", 1)[1])
        await q.edit_message_text(
            t(lang_of(uid), "admin_text_editor_title"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin.texts_editor_keyboard(page),
        )
        return
    if data == "adm_text_noop":
        return
    if data.startswith("adm_text_key:"):
        key = data.split(":", 1)[1]
        await q.edit_message_text(
            admin_text_preview(key),
            parse_mode=ParseMode.HTML,
            reply_markup=admin.text_languages_keyboard(key),
        )
        return
    if data.startswith("adm_text_lang:"):
        key, selected_lang = data.removeprefix("adm_text_lang:").rsplit(":", 1)
        if selected_lang != "en":
            await q.answer("English is the only available language.", show_alert=True)
            return
        current = db.get_text_override(key, selected_lang)
        if current is None:
            current = TRANSLATIONS.get(key, {}).get(selected_lang, "—")
        PENDING[uid] = ("adm_text_override", f"{key}|{selected_lang}")
        prompt = t(
            lang_of(uid), "admin_send_new_text",
            text_key=key, selected_lang=selected_lang, current=current,
        )
        await q.message.reply_text(
            prompt[:4000],
            reply_markup=ForceReply(
                selective=True,
                input_field_placeholder="Envoyez le nouveau texte…",
            ),
        )
        return
    if data == "adm_buttons":
        await q.edit_message_text(
            "🔘 *Gestion des boutons*\n\nCliquez sur un bouton standard pour le masquer/réactiver. Les boutons personnalisés marqués 🗑 peuvent être supprimés.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin.buttons_editor_keyboard(),
        )
        return
    if data.startswith("adm_btn_toggle:"):
        action = data.split(":", 1)[1]
        allowed = {"catalog", "topup", "orders", "account", "affiliate", "support", "language"}
        if action in allowed:
            hidden = set(filter(None, (db.get_setting("hidden_home_actions", "") or "").split(",")))
            hidden.remove(action) if action in hidden else hidden.add(action)
            db.set_setting("hidden_home_actions", ",".join(sorted(hidden)))
        await q.edit_message_reply_markup(reply_markup=admin.buttons_editor_keyboard())
        return
    if data == "adm_btn_add":
        PENDING[uid] = ("adm_btn_add", 0)
        await q.message.reply_text(
            "➕ Envoyez : `Français | English | العربية | https://exemple.com`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if data.startswith("adm_btn_del:"):
        db.delete_custom_button(int(data.split(":", 1)[1]))
        await q.edit_message_reply_markup(reply_markup=admin.buttons_editor_keyboard())
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
        PENDING[uid] = ("adm_addoff_image", sid)
        await q.message.reply_text(
            "🖼 *Nouvelle offre — étape 1/6*\n\n"
            "Envoyez l’image publicitaire de l’offre. Elle sera affichée aux clients.",
            parse_mode=ParseMode.MARKDOWN,
        )
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
    if data.startswith(("adm_offname:", "adm_offemoji:", "adm_offnote:", "adm_offdesc:", "adm_offdelay:")):
        action, oid = data.split(":")
        PENDING[uid] = (action, int(oid))
        prompts = {
            "adm_offname": "✏️ Envoyez le nouveau nom :",
            "adm_offemoji": "🎨 Envoyez un emoji Telegram Premium animé :",
            "adm_offnote": "📝 Envoyez la nouvelle note/garantie :",
            "adm_offdesc": "📄 Envoyez la description complète :",
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
    if data.startswith("adm_offimage:"):
        oid = int(data.split(":")[1])
        PENDING[uid] = ("adm_offimage", oid)
        await q.message.reply_text(
            "🖼 *Envoyez la nouvelle image publicitaire*\n\n"
            "Utilisez le bouton 📎 de Telegram, puis choisissez *Photo ou vidéo*.",
            parse_mode=ParseMode.MARKDOWN,
        )
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
    app.add_handler(MessageHandler(filters.PHOTO, handle_pending_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_menu))
    app.add_error_handler(on_error)
    return app


def main():
    app = build_app()
    log.info("HEAVENPREM bot démarré (long polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
