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
import time
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
from telegram.helpers import escape_markdown

import admin
import database as db
import keyboards as kb
from app import support_bridge
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
    CLICK_REPORT_CHAT_ID,
    CURRENCY,
    DEFAULT_LANG,
    MEMBERSHIP_CACHE_SECONDS,
    REQUIRED_CHANNEL,
    SHOP_NAME,
    SUPPORT_TICKET_CHANNEL_ID,
    USDT_EVM_ADDRESS,
    configuration_issues,
    public_base_url_from_environment,
)
from i18n import TRANSLATIONS, status_label, t

_handlers = [logging.StreamHandler()]
if not os.environ.get("VERCEL") and not os.environ.get("RAILWAY_ENVIRONMENT_ID"):
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

# Positive-only membership cache. Non-members are never cached, and the
# explicit Verify button always performs a live Telegram check.
_membership_cache: dict[tuple[int, str], float] = {}


def cache_required_channel_member(user_id: int) -> None:
    channel = str(_normalize_required_chat(REQUIRED_CHANNEL))
    if channel and MEMBERSHIP_CACHE_SECONDS > 0:
        _membership_cache[(int(user_id), channel)] = (
            time.monotonic() + MEMBERSHIP_CACHE_SECONDS
        )


async def is_required_channel_member_cached(bot, user_id: int) -> bool:
    """Avoid Telegram API round trips for recently verified members."""
    channel = str(_normalize_required_chat(REQUIRED_CHANNEL))
    key = (int(user_id), channel)
    now = time.monotonic()
    if _membership_cache.get(key, 0) > now:
        return True
    _membership_cache.pop(key, None)
    allowed = await is_required_channel_member(bot, user_id)
    if allowed:
        cache_required_channel_member(user_id)
    if len(_membership_cache) > 10_000:
        expired = [cache_key for cache_key, expiry in _membership_cache.items() if expiry <= now]
        for cache_key in expired:
            _membership_cache.pop(cache_key, None)
    return allowed

async def block_non_channel_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prevent customers from bypassing the required channel via direct commands."""
    user = update.effective_user
    if not user or user.id == ADMIN_ID:
        return
    if update.callback_query and update.callback_query.data == "verify_channel_join":
        return
    message_text = getattr(update.effective_message, "text", "") or ""
    if message_text.startswith("/start"):
        return
    if await is_required_channel_member_cached(context.bot, user.id):
        return
    lang = lang_of(user.id)
    if update.callback_query:
        await update.callback_query.answer()
    await update.effective_message.reply_text(
        premium_customer_text(lang, "channel_join_required"),
        parse_mode=ParseMode.HTML,
        reply_markup=kb.channel_join_keyboard(lang),
    )
    raise ApplicationHandlerStop

def _interaction_button_name(query):
    """Return the exact visible label of a pressed inline button when available."""
    callback_data = str(getattr(query, "data", "") or "")
    markup = getattr(getattr(query, "message", None), "reply_markup", None)
    for row in getattr(markup, "inline_keyboard", None) or []:
        for button in row:
            if str(getattr(button, "callback_data", "") or "") == callback_data:
                label = " ".join(str(getattr(button, "text", "") or "").split())
                if label:
                    return label

    action, _, value = callback_data.partition(":")
    names = {
        "home": "Main menu", "catalog": "Catalog", "catalog_request": "Request a product",
        "orders": "My orders", "account": "My account", "affiliate": "Affiliate program",
        "affiliate_copy": "Copy referral link", "support": "Support", "language": "Language",
        "topup": "Top up balance",
        "topup_txid": "Verify top-up with TXID", "topup_bsc": "Top up with BSC",
        "topup_polygon": "Top up with Polygon", "verify_channel_join": "Verify membership",
        "paid": "Verify payment with TXID",
        "paid_chain": "Submit blockchain TXID", "continue_pay": "Continue payment",
        "confirm_buy": "Create new order", "cancel_buy": "Cancel order",
        "pay_wallet": "Pay with wallet", "pay_binance": "Pay with Binance Pay",
        "pay_bsc": "Pay with USDT BSC", "pay_polygon": "Pay with USDT Polygon",
        "orders_export": "Export orders", "rating": "Rate purchase",
        "support_cat": "Support category", "support_order": "Support order",
        "svc": "Open service", "off": "Open offer", "buy": "Buy now",
        "buyq": "Select quantity", "qty_page": "Change quantity page", "tour": "Onboarding",
    }
    name = names.get(action) or action.replace("_", " ").strip().title() or "Unknown button"
    return f"{name} ({value})" if value else name


async def notify_admin_interaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send customer button clicks to the private click-report channel."""
    user = update.effective_user
    if not user or user.id == ADMIN_ID or not update.callback_query:
        return

    raw_name = user.full_name or user.first_name or "Unknown user"
    display_name = html.escape(raw_name)
    raw_username = user.username or ""
    username = f"@{html.escape(raw_username)}" if raw_username else "Not provided"
    profile = f'<a href="tg://user?id={user.id}">{display_name}</a>'
    header = (
        "<b>CUSTOMER CLICK</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Customer:</b> {profile}\n"
        f"<b>Username:</b> {username}\n"
        f"<b>Telegram ID:</b> <code>{user.id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )

    media_message = None
    if update.callback_query:
        query = update.callback_query
        raw_callback = str(query.data or "")
        button_name = _interaction_button_name(query)
        source_text = (
            getattr(query.message, "text", None)
            or getattr(query.message, "caption", None)
            or ""
        )
        details = (
            "<b>Interaction:</b> Button click\n"
            f"<b>Button:</b> {html.escape(button_name[:200])}\n"
            f"<b>Action code:</b> <code>{html.escape(raw_callback[:500])}</code>"
        )
        if source_text:
            details += (
                "\n\n<b>Screen before the click:</b>\n"
                f"<blockquote>{html.escape(source_text[:1200])}</blockquote>"
            )
        interaction_type = "button"
        interaction_action = raw_callback
        interaction_content = button_name
        interaction_screen = source_text
    elif update.effective_message:
        message = update.effective_message
        content = message.text or message.caption or ""
        if content:
            interaction_type = "command" if str(content).startswith("/") else "message"
            type_name = "Command" if interaction_type == "command" else "Text message"
            interaction_action = str(content).split(maxsplit=1)[0] if interaction_type == "command" else ""
            interaction_content = content
            details = (
                f"<b>Interaction:</b> {type_name}\n"
                "<b>Customer sent:</b>\n"
                f"<blockquote>{html.escape(content[:2500])}</blockquote>"
            )
        elif getattr(message, "photo", None):
            details = "<b>Interaction:</b> Photo\n<b>Customer sent:</b> A photo (copied below)"
            interaction_type, interaction_action, interaction_content = "media", "photo", "Photo"
            media_message = message
        elif getattr(message, "document", None):
            document = message.document
            filename = html.escape(str(getattr(document, "file_name", "") or "Unnamed file"))
            details = f"<b>Interaction:</b> Document\n<b>Customer sent:</b> {filename} (copied below)"
            interaction_type, interaction_action, interaction_content = "media", "document", filename
            media_message = message
        elif getattr(message, "video", None):
            details = "<b>Interaction:</b> Video\n<b>Customer sent:</b> A video (copied below)"
            interaction_type, interaction_action, interaction_content = "media", "video", "Video"
            media_message = message
        elif getattr(message, "voice", None):
            details = "<b>Interaction:</b> Voice message\n<b>Customer sent:</b> A voice message (copied below)"
            interaction_type, interaction_action, interaction_content = "media", "voice", "Voice message"
            media_message = message
        else:
            details = "<b>Interaction:</b> Other message\n<b>Customer sent:</b> Unsupported Telegram content"
            interaction_type, interaction_action, interaction_content = "other", "unsupported", "Unsupported content"
        interaction_screen = ""
    else:
        return

    try:
        db.log_interaction(
            user.id,
            first_name=user.first_name or "",
            full_name=raw_name,
            username=raw_username,
            interaction_type=interaction_type,
            action=interaction_action,
            content=interaction_content,
            screen=interaction_screen,
        )
    except Exception:
        log.exception("Unable to persist interaction from user %s", user.id)

    try:
        await context.bot.send_message(
            CLICK_REPORT_CHAT_ID,
            f"{header}{details}",
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        if media_message and hasattr(context.bot, "copy_message"):
            chat = getattr(media_message, "chat", None)
            chat_id = getattr(chat, "id", None) or getattr(media_message, "chat_id", None)
            message_id = getattr(media_message, "message_id", None)
            if chat_id and message_id:
                await context.bot.copy_message(
                    chat_id=CLICK_REPORT_CHAT_ID,
                    from_chat_id=chat_id,
                    message_id=message_id,
                )
    except Exception:
        log.exception("Unable to notify admin about interaction from user %s", user.id)

async def block_banned_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and user.id != ADMIN_ID and db.is_user_banned(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔ Accès suspendu.", show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text("⛔ Votre accès à cette boutique est suspendu.")
        raise ApplicationHandlerStop


async def block_maintenance_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lock the entire customer bot during maintenance while preserving admin access."""
    user = update.effective_user
    if not user or user.id == ADMIN_ID:
        return
    settings = db.shop_settings()
    if not settings["maintenance_enabled"]:
        return

    message = settings["maintenance_message"].strip() or (
        "The bot is temporarily under maintenance. Please try again later."
    )
    if update.callback_query:
        await update.callback_query.answer("Maintenance mode is active.", show_alert=True)
    if update.effective_message:
        await update.effective_message.reply_text(
            "🛠️ <b>BOT UNDER MAINTENANCE</b>\n\n"
            f"{html.escape(message)}\n\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML,
        )
    raise ApplicationHandlerStop





def numbered_delivery_content(items):
    """Number delivered accounts without exposing the # import delimiter."""
    cleaned = []
    for item in items or []:
        value = str(item).strip()
        if value.startswith("#"):
            first_line, separator, remainder = value.partition("\n")
            marker_suffix = first_line[1:].strip()
            if marker_suffix and not marker_suffix.isdigit():
                value = marker_suffix + (separator + remainder if separator else "")
            else:
                value = remainder.strip()
        if value:
            cleaned.append(value)
    return "\n\n".join(f"{index}.\n{value}" for index, value in enumerate(cleaned, start=1))

def lang_of(user_id):
    return db.get_user_lang(user_id) or DEFAULT_LANG


async def notify_successful_referral(context, referrer_id):
    """Notify the referrer after every valid referral and each reward milestone."""
    stats = affiliate_service.get_stats(referrer_id)
    lang = lang_of(referrer_id)
    target = affiliate_service.REFERRAL_TARGET
    if stats["referrals"] and stats["referrals"] % target == 0:
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
        f"📦 <b>{stock_label}:</b> {'∞' if offer.get('unlimited_stock') else int(offer.get('stock') or 0)}\n"
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
        rendered = raw_value.removeprefix("[[HTML]]")
        if parse_legacy_markdown:
            rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
            rendered = re.sub(r"\*([^*]+)\*", r"<b>\1</b>", rendered)
            rendered = re.sub(r"_([^_]+)_", r"<i>\1</i>", rendered)
        return rendered
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
def _normalize_required_chat(chat):
    """Convert channel/group config into a Telegram get_chat_member target."""
    chat = str(chat or "").strip()
    if not chat:
        return ""
    if chat.startswith("https://t.me/"):
        chat = chat.removeprefix("https://t.me/").strip("/")
    elif chat.startswith("http://t.me/"):
        chat = chat.removeprefix("http://t.me/").strip("/")
    elif chat.startswith("t.me/"):
        chat = chat.removeprefix("t.me/").strip("/")
    if "/" in chat:
        chat = chat.split("/", 1)[0]
    if re.fullmatch(r"-?\d+", chat):
        return int(chat)
    if chat.startswith("@"):
        return chat
    return f"@{chat}"


async def is_required_channel_member(bot, user_id):
    """Return whether a customer belongs to the required official channel."""
    allowed, _details = await required_membership_status(bot, user_id)
    return allowed


async def required_membership_status(bot, user_id):
    """Return membership result plus per-chat diagnostics for admins/logs."""
    if user_id == ADMIN_ID:
        return True, []
    required_chats = [
        normalized
        for chat in (REQUIRED_CHANNEL,)
        if (normalized := _normalize_required_chat(chat))
    ]
    if not required_chats:
        return True, []
    details = []
    for chat in required_chats:
        resolved_chat = chat
        chat_title = str(chat)
        try:
            # Resolving public usernames first avoids unreliable username-based
            # getChatMember lookups and continues working if Telegram changes
            # the public username while the numeric chat ID stays the same.
            if hasattr(bot, "get_chat"):
                chat_info = await bot.get_chat(chat)
                resolved_chat = chat_info.id
                chat_title = (
                    getattr(chat_info, "title", None)
                    or getattr(chat_info, "full_name", None)
                    or str(chat)
                )

            member = None
            last_error = None
            for attempt in range(2):
                try:
                    member = await bot.get_chat_member(resolved_chat, user_id)
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt == 0:
                        await asyncio.sleep(0.25)
            if member is None:
                raise last_error
        except Exception as exc:
            log.warning("Unable to verify membership in %s for %s: %s", chat, user_id, exc)
            detail = {"chat": chat, "ok": False, "error": str(exc)}
            if resolved_chat != chat:
                detail["chat_id"] = resolved_chat
            if chat_title != str(chat):
                detail["title"] = chat_title
            details.append(detail)
            continue
        status = getattr(getattr(member, "status", None), "value", getattr(member, "status", ""))
        status = str(status).lower()
        is_member = status in {"creator", "owner", "administrator", "member"} or (
            status == "restricted" and bool(getattr(member, "is_member", False))
        )
        detail = {"chat": chat, "ok": is_member, "status": status}
        if resolved_chat != chat:
            detail["chat_id"] = resolved_chat
        if chat_title != str(chat):
            detail["title"] = chat_title
        details.append(detail)
    return all(detail["ok"] for detail in details), details


def _format_membership_diagnostics(user_id, details):
    if not details:
        return f"Membership verification failed for <code>{user_id}</code>: no required chats configured."
    lines = [f"Membership verification failed for <code>{user_id}</code>:"]
    for detail in details:
        chat = html.escape(str(detail.get("chat", "")))
        title = html.escape(str(detail.get("title", "")))
        chat_id = html.escape(str(detail.get("chat_id", "")))
        identity = f"<code>{chat}</code>"
        if title and title != chat:
            identity += f" ({title})"
        if chat_id and chat_id != chat:
            identity += f" [<code>{chat_id}</code>]"
        if detail.get("error"):
            error = html.escape(str(detail["error"])[:500])
            lines.append(f"- {identity}: API error: {error}")
        else:
            status = html.escape(str(detail.get("status", "unknown")))
            result = "OK" if detail.get("ok") else "NOT JOINED"
            lines.append(f"- {identity}: {result}, status=<code>{status}</code>")
    return "\n".join(lines)


async def register_start_referral(context, referred_id, referrer_id):
    """Register a preserved start-link referral for later purchase qualification."""
    if not referrer_id:
        return
    affiliate_service.register_referral_link(referred_id, int(referrer_id))


async def send_channel_member_welcome(send, context, user_id, lang):
    """Show the post-verification marketing welcome and unlock the main menu."""
    username = context.bot.username or (await context.bot.get_me()).username
    referral_link = f"https://t.me/{username}?start=ref_{user_id}"
    await send(
        premium_customer_text(
            lang, "channel_member_welcome", shop=SHOP_NAME, link=referral_link,
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb.home_keyboard(lang, user_id),
    )


async def announce_channel_restock(context, offer_id, added, stock):
    """Broadcast a private new-stock advert to every active bot user."""
    offer = db.get_offer(int(offer_id))
    if not offer or not offer.get("active", 1):
        return 0
    unlimited = bool(offer.get("unlimited_stock"))
    if not unlimited and int(stock or 0) <= 0:
        return 0
    if added is not None and int(added or 0) <= 0:
        return 0
    service = db.get_service(offer["service_id"]) or {}
    price = "—" if offer.get("price") is None else f"{float(offer['price']):.2f}"
    sent = 0
    for user in db.list_broadcast_users():
        user_id = user.get("telegram_id")
        if not user_id:
            continue
        lang = user.get("lang") or DEFAULT_LANG
        try:
            message_key = (
                "channel_stock_announcement"
                if added is not None
                else "offer_stock_announcement"
            )
            values = {
                "emoji": service.get("emoji") or "📦",
                "service": service.get("name") or SHOP_NAME,
                "offer": offer.get("name") or f"Offer #{offer_id}",
                "price": price,
                "cur": CURRENCY,
                "stock": "∞" if unlimited else int(stock),
            }
            if added is not None:
                values["added"] = int(added)
            await context.bot.send_message(
                chat_id=user_id,
                text=premium_customer_text(
                    lang,
                    message_key,
                    **values,
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.offer_detail_keyboard(lang, offer),
            )
            sent += 1
        except Exception as exc:
            # Telegram rejects future messages when a user blocks/deletes the bot.
            message = str(exc).lower()
            if "blocked" in message or "chat not found" in message or "deactivated" in message:
                db.mark_broadcast_blocked(user_id)
            else:
                log.warning("New-stock broadcast failed for user %s: %s", user_id, exc)
        await asyncio.sleep(0.04)
    return sent


async def send_new_stock_broadcast(context, offer_id, added, stock):
    """Finish the broadcast before a serverless webhook request can terminate."""
    return await announce_channel_restock(context, offer_id, added, stock)


async def announce_flash_sale(context, offer_id):
    """Broadcast an active flash sale privately to every active bot user."""
    offer = db.get_offer(int(offer_id))
    if not offer or not offer.get("active", 1) or not offer.get("flash_sale_active"):
        return 0
    service = db.get_service(offer["service_id"]) or {}
    remaining_seconds = max(0, int(offer["flash_sale_ends_at"]) - int(time.time()))
    hours, remainder = divmod(remaining_seconds, 3600)
    minutes = max(1, remainder // 60)
    remaining = f"{hours}h {minutes}m" if hours else f"{minutes}m"
    sent = 0
    for user in db.list_broadcast_users():
        user_id = user.get("telegram_id")
        if not user_id:
            continue
        lang = user.get("lang") or DEFAULT_LANG
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=premium_customer_text(
                    lang,
                    "flash_sale_announcement",
                    emoji=service.get("emoji") or "🎁",
                    offer=offer.get("name") or f"Offer #{offer_id}",
                    old_price=f"{float(offer['flash_sale_original_price']):.2f}",
                    price=f"{float(offer['price']):.2f}",
                    cur=CURRENCY,
                    remaining=remaining,
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.offer_detail_keyboard(lang, offer),
            )
            sent += 1
        except Exception as exc:
            message = str(exc).lower()
            if "blocked" in message or "chat not found" in message or "deactivated" in message:
                db.mark_broadcast_blocked(user_id)
            else:
                log.warning("Flash-sale broadcast failed for user %s: %s", user_id, exc)
        await asyncio.sleep(0.04)
    return sent


async def announce_api_flash_sale(context, event):
    """Broadcast a supplier-driven price drop without creating a temporary price."""
    offer = db.get_offer(int(event["offer_id"]))
    if not offer or not offer.get("active", 1) or not db.offer_has_stock(offer):
        return 0
    service = db.get_service(offer["service_id"]) or {}
    old_price = float(event["previous_price"])
    new_price = float(event["price"])
    discount_percent = round(((old_price - new_price) / old_price) * 100) if old_price else 0
    sent = 0
    for user in db.list_broadcast_users():
        user_id = user.get("telegram_id")
        if not user_id:
            continue
        lang = user.get("lang") or DEFAULT_LANG
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=premium_customer_text(
                    lang,
                    "api_flash_sale_announcement",
                    emoji=service.get("emoji") or "🔥",
                    service=service.get("name") or SHOP_NAME,
                    offer=offer.get("name") or f"Offer #{offer['id']}",
                    old_price=f"{old_price:.2f}",
                    price=f"{new_price:.2f}",
                    cur=CURRENCY,
                    discount=discount_percent,
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.offer_detail_keyboard(lang, offer),
            )
            sent += 1
        except Exception as exc:
            message = str(exc).lower()
            if "blocked" in message or "chat not found" in message or "deactivated" in message:
                db.mark_broadcast_blocked(user_id)
            else:
                log.warning("API flash-sale broadcast failed for user %s: %s", user_id, exc)
        await asyncio.sleep(0.04)
    return sent


async def broadcast_admin_message(context, source_chat_id, message_id):
    """Copy an admin-authored Telegram message to every active bot user."""
    sent = 0
    for user in db.list_broadcast_users():
        user_id = user.get("telegram_id")
        if not user_id:
            continue
        try:
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=source_chat_id,
                message_id=message_id,
            )
            sent += 1
        except Exception as exc:
            message = str(exc).lower()
            if "blocked" in message or "chat not found" in message or "deactivated" in message:
                db.mark_broadcast_blocked(user_id)
            else:
                log.warning("Admin announcement failed for user %s: %s", user_id, exc)
        await asyncio.sleep(0.04)
    return sent


async def broadcast_maintenance_notice(context, message):
    """Notify every active bot user when maintenance mode is enabled."""
    sent = 0
    for user in db.list_broadcast_users():
        user_id = user.get("telegram_id")
        if not user_id:
            continue
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🛠️ Maintenance\n\n{message}",
            )
            sent += 1
        except Exception as exc:
            error = str(exc).lower()
            if "blocked" in error or "chat not found" in error or "deactivated" in error:
                db.mark_broadcast_blocked(user_id)
            else:
                log.warning("Maintenance notice failed for user %s: %s", user_id, exc)
        await asyncio.sleep(0.04)
    return sent


async def broadcast_affiliate_program_update(context):
    """Notify every active bot user about the affiliate qualification rule."""
    sent = 0
    for user in db.list_broadcast_users():
        user_id = user.get("telegram_id")
        if not user_id:
            continue
        lang = user.get("lang") or DEFAULT_LANG
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=premium_customer_text(lang, "affiliate_program_update"),
                parse_mode=ParseMode.HTML,
            )
            sent += 1
        except Exception as exc:
            error = str(exc).lower()
            if "blocked" in error or "chat not found" in error or "deactivated" in error:
                db.mark_broadcast_blocked(user_id)
            else:
                log.warning("Affiliate program update failed for user %s: %s", user_id, exc)
        await asyncio.sleep(0.04)
    return sent


async def announce_channel_purchase(context, order_id):
    """Compatibility no-op: purchase results stay in the private bot chat."""
    return False


async def safely_announce_channel_purchase(context, order_id):
    return False

async def show_deep_link_offer(update, lang, offer_id):
    """Open one channel-advertised offer safely in the customer's private chat."""
    offer = db.get_offer(int(offer_id))
    if not offer or not db.offer_has_stock(offer):
        await update.message.reply_text(
            premium_customer_text(lang, "out_of_stock"), parse_mode=ParseMode.HTML,
        )
        return
    detail_text = compact_offer_text(offer, lang)
    markup = kb.offer_detail_keyboard(lang, offer)
    if offer.get("photo_file_id"):
        if len(detail_text) <= 900:
            await update.message.reply_photo(
                photo=offer["photo_file_id"], caption=detail_text,
                parse_mode=ParseMode.HTML, reply_markup=markup,
            )
        else:
            await update.message.reply_photo(photo=offer["photo_file_id"])
            await update.message.reply_text(
                detail_text, parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True), reply_markup=markup,
            )
        return
    await update.message.reply_text(
        detail_text, parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True), reply_markup=markup,
    )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    is_new = db.upsert_user(u.id, u.username or "", u.first_name or "")
    lang = DEFAULT_LANG
    if db.get_user_lang(u.id) != DEFAULT_LANG:
        db.set_user_lang(u.id, DEFAULT_LANG)

    pending = PENDING.get(u.id)
    referrer_id = pending[1] if pending and pending[0] == "await_channel_join" else 0
    if context.args and context.args[0].startswith("ref_"):
        with contextlib.suppress(ValueError, TypeError):
            referrer_id = int(context.args[0][4:])

    if u.id != ADMIN_ID and not await is_required_channel_member_cached(context.bot, u.id):
        PENDING[u.id] = ("await_channel_join", referrer_id)
        await update.message.reply_text(
            premium_customer_text(lang, "channel_join_required"),
            parse_mode=ParseMode.HTML,
            reply_markup=kb.channel_join_keyboard(lang),
        )
        return

    if pending and pending[0] == "await_channel_join":
        PENDING.pop(u.id, None)
    await register_start_referral(context, u.id, referrer_id)

    if is_new:
        await send_channel_member_welcome(update.message.reply_text, context, u.id, lang)
    elif context.args and context.args[0].startswith("offer_"):
        try:
            offer_id = int(context.args[0].split("_", 1)[1])
        except (ValueError, IndexError):
            await show_catalog(update, context, lang)
        else:
            await show_deep_link_offer(update, lang, offer_id)
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
    public_base_url = public_base_url_from_environment()
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


def ticket_conversation_text(ticket):
    category = str(ticket.get("category") or "other").replace("_", " ").title()
    return (
        f"<b>Support Ticket {support_bridge.ticket_reference(ticket['id'])}</b>\n\n"
        f"<blockquote>Category: <b>{html.escape(category)}</b>\n"
        "Status: <b>Open</b></blockquote>\n\n"
        "Send any message or attachment here. It goes directly to our support team."
    )


async def send_ticket_conversation(message, lang, ticket):
    await message.reply_text(
        ticket_conversation_text(ticket),
        parse_mode=ParseMode.HTML,
        reply_markup=kb.ticket_conversation_keyboard(lang, ticket["id"]),
    )


async def delete_customer_support_message(message):
    """Remove a customer's original message after it reaches support."""
    with contextlib.suppress(Exception):
        await message.delete()


async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_user.id)
    await update.effective_message.reply_text(
        t(lang, "support_choose_category"),
        reply_markup=kb.support_category_keyboard(lang),
    )


async def cmd_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_catalog(update, context, lang_of(update.effective_user.id))


async def show_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = lang_of(uid)
    await update.effective_message.reply_text(
        premium_customer_text(lang, "topup_message", binance_id=BINANCE_PAY_ID),
        parse_mode=ParseMode.HTML,
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
        "await_onchain_txid",
        "await_topup_txid",
        "await_onchain_topup_amount",
        "await_onchain_topup_txid",
        "otp_service",
        "otp_country",
        "await_quantity",
        "catalog_request",
        "adm_setprice",
        "adm_flash_start",
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
        "adm_manual_stock",
        "adm_broadcast_message",
        "adm_deliver",
    }

    if pending and pending[0] in blocking_states:
        await handle_pending_input(update, context, lang)
        return
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
    elif pending and pending[0].startswith(("support", "ticket_")):
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

    if data == "verify_channel_join":
        allowed, details = await required_membership_status(context.bot, uid)
        if not allowed:
            log.info("%s", _format_membership_diagnostics(uid, details))
            await q.edit_message_text(
                premium_customer_text(lang, "channel_join_not_verified"),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.channel_join_keyboard(lang),
            )
            return
        cache_required_channel_member(uid)
        pending = PENDING.pop(uid, None)
        referrer_id = pending[1] if pending and pending[0] == "await_channel_join" else 0
        db.set_user_lang(uid, DEFAULT_LANG)
        await register_start_referral(context, uid, referrer_id)
        await send_channel_member_welcome(q.edit_message_text, context, uid, DEFAULT_LANG)
        return
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
    if data == "catalog_request":
        PENDING[uid] = ("catalog_request", 0)
        await q.message.reply_text(
            premium_customer_text(lang, "catalog_request_prompt"),
            parse_mode=ParseMode.HTML,
        )
        return
    if data == "orders":
        await show_my_orders(update, context, lang)
        return
    if data == "topup":
        await show_topup(update, context)
        return
    if data in {"topup_bsc", "topup_polygon"}:
        network = "bsc" if data == "topup_bsc" else "polygon"
        network_label = "BSC (BEP20)" if network == "bsc" else "Polygon"
        PENDING[uid] = ("await_onchain_topup_amount", network)
        await q.message.reply_text(
            t(lang, "topup_onchain_amount", network=network_label),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if data in {"topup_txid", "topup_claim"}:
        # Older messages used topup_claim for the removed automatic scan.
        # Keep them useful by routing directly to TXID entry.
        PENDING[uid] = ("await_topup_txid", 0)
        await q.message.reply_text(
            premium_customer_text(lang, "topup_ask_txid"),
            parse_mode=ParseMode.HTML,
        )
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
        service = db.get_service(sid)
        if not service:
            await show_callback_screen(
                q,
                t(lang, "catalog_title", shop=SHOP_NAME),
                reply_markup=kb.services_keyboard(lang),
            )
            return
        emoji = service.get("emoji", "📦")
        name = service.get("name", "")
        await show_callback_screen(
            q,
            t(lang, "service_title", emoji=emoji, name=name),
            reply_markup=kb.offers_keyboard(lang, sid),
        )
        return
    if data.startswith("off:"):
        oid = int(data.split(":")[1])
        off = db.get_offer(oid)
        if not off or not db.offer_has_stock(off):
            await q.message.reply_text(
                premium_customer_text(lang, "out_of_stock"),
                parse_mode=ParseMode.HTML,
            )
            return
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
            base_url = public_base_url_from_environment()
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
    if data.startswith((
        "confirm_buy:", "pay_wallet:", "pay_binance:", "pay_bsc:", "pay_polygon:",
    )):
        payment_method = (
            "wallet" if data.startswith("pay_wallet:")
            else "usdt_bsc" if data.startswith("pay_bsc:")
            else "usdt_polygon" if data.startswith("pay_polygon:")
            else "binance"
        )
        await handle_buy_confirmed(update, context, lang, payment_method=payment_method)
        return
    if data.startswith("cancel_buy:"):
        order_id = int(data.split(":", 1)[1])
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
    if data.startswith(("paid:", "verify_auto:")):
        # Older order messages may still contain verify_auto. Automatic
        # matching is gone; route that legacy button to TXID entry instead.
        oid = int(data.split(":")[1])
        PENDING[uid] = ("await_txid", oid)
        await q.message.reply_text(t(lang, "ask_txid", oid=oid),
                                   parse_mode=ParseMode.MARKDOWN)
        return
    if data.startswith("paid_chain:"):
        oid = int(data.split(":", 1)[1])
        order = db.get_order(oid)
        if not order or order.get("user_id") != uid:
            await q.answer(t(lang, "not_for_you"), show_alert=True)
            return
        network = (
            "BSC (BEP20)"
            if order.get("payment_method") == "usdt_bsc"
            else "Polygon"
        )
        PENDING[uid] = ("await_onchain_txid", {"order_id": oid, "network": network})
        await q.message.reply_text(
            t(lang, "ask_onchain_txid", oid=oid, network=network),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if data.startswith("continue_pay:"):
        oid = int(data.split(":")[1])
        order = db.get_order(oid)
        if order and order["user_id"] == uid:
            onchain = order.get("payment_method") in {"usdt_bsc", "usdt_polygon"}
            text = (
                onchain_payment_screen(lang, order)
                if onchain
                else premium_customer_text(
                    lang, "order_created", oid=oid, service=order["service_name"],
                    offer=order["offer_name"], qty=order["qty"],
                    total=f"{order['total_price']:.2f}", cur=CURRENCY,
                    binance_id=BINANCE_PAY_ID,
                )
            )
            await q.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN if onchain else ParseMode.HTML,
                reply_markup=(
                    kb.onchain_payment_keyboard(lang, oid)
                    if onchain
                    else kb.paid_keyboard(
                        lang, oid, BINANCE_PAY_ID,
                        f"{order['total_price']:.2f}", CURRENCY,
                    )
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
    if data.startswith("ticket_close:"):
        ticket_id = int(data.split(":", 1)[1])
        ticket = support_service.get_ticket(ticket_id)
        if not ticket or int(ticket.get("user_id") or 0) != uid:
            await q.answer(t(lang, "not_for_you"), show_alert=True)
            return
        support_service.close_ticket(ticket_id)
        pending = PENDING.get(uid)
        if pending and pending[0] == "ticket_message" and int(pending[1]) == ticket_id:
            PENDING.pop(uid, None)
        await q.edit_message_text(
            f"<b>Support Ticket {support_bridge.ticket_reference(ticket_id)}</b>\n\n"
            "Status: <b>Closed</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.home_keyboard(lang, uid),
        )
        await support_bridge.send_ticket_closed(context, ticket, q.from_user)
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

    if not offer or offer["price"] is None or not db.offer_has_stock(offer):
        await q.answer(t(lang, "out_of_stock"), show_alert=True)
        return

    PENDING[q.from_user.id] = ("await_quantity", offer_id)
    send_quantity_prompt = q.message.reply_text if q.message.photo else q.edit_message_text
    await send_quantity_prompt(
        t(
            lang,
            "choose_quantity",
            offer=offer["name"],
            stock="∞" if offer.get("unlimited_stock") else offer["stock"],
            price=f"{offer['price']:.2f}",
            cur=CURRENCY,
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


async def send_buy_confirmation(send, uid, offer_id, qty, lang):
    """Validate a typed quantity and display the purchase summary."""
    offer = db.get_offer(offer_id)
    if not offer or offer["price"] is None or not db.offer_has_stock(offer, qty):
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
        await q.message.reply_text(t(lang, "out_of_stock"))


def onchain_payment_screen(lang, order):
    method = order.get("payment_method")
    network = "BSC (BEP20)" if method == "usdt_bsc" else "Polygon"
    contract_warning = (
        "Verify that the USDT contract address ends in *97955*."
        if method == "usdt_bsc"
        else "Verify that the USDT contract address ends in *58e8f*."
    )
    return t(
        lang, "onchain_order_created",
        oid=order["id"], offer=order["offer_name"], qty=order["qty"],
        total=f"{order['total_price']:.2f}", network=network,
        address=USDT_EVM_ADDRESS, contract_warning=contract_warning,
    )


async def handle_buy_confirmed(update, context, lang, payment_method="binance"):
    """Cr?e la commande apr?s confirmation de l'utilisateur."""
    q = update.callback_query
    uid = q.from_user.id
    parts = q.data.split(":")
    offer_id = int(parts[1])
    qty = int(parts[2]) if len(parts) > 2 else 1
    offer = db.get_offer(offer_id)

    if not offer or offer["price"] is None or not db.offer_has_stock(offer, qty):
        await q.message.reply_text(t(lang, "out_of_stock"))
        return

    try:
        order = order_service.create_order(uid, offer, qty=qty, payment_method=payment_method)
        order_service.cancel_incomplete_orders(uid, exclude_order_id=order["id"])
    except ValueError as exc:
        # cb_navigation already acknowledged this callback. Telegram rejects a
        # second q.answer(), which previously left wallet errors invisible.
        await q.message.reply_text(str(exc))
        return

    if order["total_price"] == 0:
        await q.edit_message_text(t(lang, "wallet_payment_processing"), parse_mode=ParseMode.MARKDOWN)
        result = await asyncio.to_thread(payment_service.confirm_wallet_order, order["id"], uid)
        await send_payment_result(q.message, context, lang, order["id"], result, uid)
        return

    if payment_method in {"usdt_bsc", "usdt_polygon"}:
        await q.edit_message_text(
            onchain_payment_screen(lang, order),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.onchain_payment_keyboard(lang, order["id"]),
        )
        return

    text = premium_customer_text(
        lang, "order_created", oid=order["id"], service=order["service_name"],
        offer=order["offer_name"], qty=order["qty"],
        total=f"{order['total_price']:.2f}", cur=CURRENCY,
        binance_id=BINANCE_PAY_ID,
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
        stock = "∞" if (offer or {}).get("unlimited_stock") else int((offer or {}).get("stock") or 0)
        if not db.offer_has_stock(offer, qty):
            await update.message.reply_text(
                t(lang, "quantity_invalid", stock=stock),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        PENDING.pop(uid, None)
        await send_buy_confirmation(update.message.reply_text, uid, int(ref), qty, lang)
        return

    if kind == "otp_service":
        order_id = int(ref["order_id"] if isinstance(ref, dict) else ref)
        order = db.get_order(order_id)
        if not order or order.get("user_id") != uid or order.get("status") not in {
            "paid", "payment_confirmed", "delivered",
        }:
            PENDING.pop(uid, None)
            await update.message.reply_text(t(lang, "otp_order_unavailable"))
            return
        service_name = " ".join(text.split())[:120]
        if not service_name:
            await update.message.reply_text(t(lang, "otp_ask_service"))
            return
        db.get_conn().orders.update_one(
            {"id": order_id},
            {"$set": {
                "otp_service": service_name,
                "otp_workflow_status": "awaiting_country",
                "updated_at": int(time.time()),
            }},
        )
        PENDING[uid] = (
            "otp_country",
            {"order_id": order_id, "service": service_name},
        )
        await update.message.reply_text(
            t(lang, "otp_ask_country", service=escape_markdown(service_name)),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if kind == "otp_country":
        order_id = int(ref["order_id"])
        service_name = str(ref["service"])
        order = db.get_order(order_id)
        if not order or order.get("user_id") != uid or order.get("status") not in {
            "paid", "payment_confirmed", "delivered",
        }:
            PENDING.pop(uid, None)
            await update.message.reply_text(t(lang, "otp_order_unavailable"))
            return
        country = " ".join(text.split())[:80]
        if not country:
            await update.message.reply_text(
                t(lang, "otp_ask_country", service=escape_markdown(service_name)),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        now = int(time.time())
        db.get_conn().orders.update_one(
            {"id": order_id},
            {"$set": {
                "otp_service": service_name,
                "otp_country": country,
                "otp_workflow_status": "sent_to_admin",
                "otp_requested_at": now,
                "updated_at": now,
            }},
        )
        PENDING.pop(uid, None)
        user = update.effective_user
        username = f"@{user.username}" if getattr(user, "username", None) else "?"
        display_name = getattr(user, "full_name", None) or username or str(uid)
        request_details = f"Service: {service_name}\nCountry: {country}"
        ticket = support_service.create_ticket(
            uid,
            request_details,
            category="otp_order",
            order_id=order_id,
        )
        admin_text = (
            "<b>New paid OTP request</b>\n\n"
            f"Order: <b>#{order_id}</b>\n"
            f"Client: <b>{html.escape(str(display_name))}</b>\n"
            f"Username: <b>{html.escape(username)}</b>\n"
            f"Telegram ID: <code>{uid}</code>\n"
            f"Quantity: <b>{int(order.get('qty') or 1)} OTP code(s)</b>\n"
            f"Total paid: <b>{float(order.get('wallet_amount') or order.get('total_price') or 0):.2f} {CURRENCY}</b>\n"
            f"Payment: <b>{html.escape(str(order.get('verify_method') or order.get('payment_method') or 'confirmed'))}</b>\n"
            f"TXID: <code>{html.escape(str(order.get('txid') or 'wallet payment'))}</code>\n"
            f"Requested service: <b>{html.escape(service_name)}</b>\n"
            f"Country: <b>{html.escape(country)}</b>\n"
            f"Support ticket: <b>#{ticket['id']}</b>"
        )
        try:
            await context.bot.send_message(
                ADMIN_ID,
                admin_text,
                parse_mode=ParseMode.HTML,
                reply_markup=admin.manual_delivery_request_keyboard(order_id),
            )
        except Exception as exc:
            log.warning("OTP order #%s admin notification failed: %s", order_id, exc)
        await update.message.reply_text(
            t(
                lang,
                "otp_redirect_admin",
                oid=order_id,
                service=escape_markdown(service_name),
                country=escape_markdown(country),
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.home_keyboard(lang, uid),
        )
        return
    if kind == "catalog_request":
        request_text = rich_text_from_message(update.message).strip()
        if not request_text:
            await update.message.reply_text(
                premium_customer_text(lang, "catalog_request_prompt"),
                parse_mode=ParseMode.HTML,
            )
            return
        ticket = support_service.create_ticket(uid, request_text, category="catalog_request")
        PENDING.pop(uid, None)
        await support_bridge.send_client_text(
            context,
            ticket,
            update.effective_user,
            request_text,
            event="New catalog request",
        )
        await update.message.reply_text(
            premium_customer_text(lang, "catalog_request_sent"),
            parse_mode=ParseMode.HTML,
            reply_markup=kb.home_keyboard(lang, uid),
        )
        await delete_customer_support_message(update.message)
        log.info("Catalog request ticket %s created by user %s", ticket["id"], uid)
        return

    if kind == "adm_flash_start" and uid == ADMIN_ID:
        try:
            parts = text.replace(",", ".").split()
            if len(parts) != 2:
                raise ValueError("Format attendu : prix puis durée.")
            sale_price = float(parts[0])
            duration_minutes = int(parts[1])
            offer = db.start_flash_sale(ref, sale_price, duration_minutes)
        except (TypeError, ValueError) as exc:
            await update.message.reply_text(
                f"⚠️ Valeurs invalides. Envoyez : `prix durée_en_minutes`\n"
                f"Exemple : `3 480`\n\n{exc}",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        PENDING.pop(uid, None)
        sent = await announce_flash_sale(context, ref)
        await update.message.reply_text(
            f"⚡ Vente flash lancée pour *{offer['name']}*.\n"
            f"Prix : *{offer['flash_sale_original_price']:.2f} → {offer['price']:.2f} {CURRENCY}*\n"
            f"Annonce envoyée à *{sent} utilisateur(s)*.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin.offer_admin_keyboard(ref),
        )
        return

    if kind == "adm_broadcast_message" and uid == ADMIN_ID:
        PENDING.pop(uid, None)
        sent = await broadcast_admin_message(
            context,
            update.effective_chat.id,
            update.message.message_id,
        )
        await update.message.reply_text(
            f"✅ Annonce envoyée à {sent} utilisateur(s).",
            reply_markup=admin.admin_panel_keyboard(),
        )
        return
    if kind == "adm_text_override" and uid == ADMIN_ID:
        saved_key = ""
        override_icon = custom_emoji_from_message(update.message)
        override_text = (
            text_without_custom_emojis(update.message)
            if kb.is_button_text_key(ref.rsplit("|", 1)[0] if isinstance(ref, str) and "|" in ref else "")
            else rich_text_from_message(update.message)
        )
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

    if kind == "await_onchain_txid":
        order_id = int(ref["order_id"])
        result = await asyncio.to_thread(
            payment_service.submit_onchain_payment, order_id, text, uid,
        )
        if result["status"] != "manual_review":
            await update.message.reply_text(
                result.get("error_message") or "Invalid transaction ID.",
            )
            return
        PENDING.pop(uid, None)
        await update.message.reply_text(
            t(
                lang, "onchain_payment_submitted",
                oid=order_id, network=result["network"],
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.orders_keyboard(lang),
        )
        with contextlib.suppress(Exception):
            await context.bot.send_message(
                ADMIN_ID,
                "🔎 <b>On-chain payment review</b>\n"
                f"Order: <b>#{order_id}</b>\n"
                f"Network: <b>{html.escape(result['network'])}</b>\n"
                f"Amount: <b>{float(result['order']['total_price']):.2f} USDT</b>\n"
                f"TXID: <code>{html.escape(text)}</code>",
                parse_mode=ParseMode.HTML,
            )
        return

    if kind == "await_topup_txid":
        result = await asyncio.to_thread(wallet_service.claim_transfer, uid, text)
        if result["status"] == "confirmed":
            PENDING.pop(uid, None)
            await update.message.reply_text(
                premium_customer_text(lang, "topup_success", amount=f"{result['amount']:.2f}", balance=f"{result['balance']:.2f}"),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.home_keyboard(lang, uid),
            )
        elif result.get("code") == "already_used":
            PENDING.pop(uid, None)
            await update.message.reply_text(
                premium_customer_text(lang, "topup_already_confirmed"),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.home_keyboard(lang, uid),
            )
        else:
            await update.message.reply_text(
                premium_customer_text(lang, "topup_failed"),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.topup_keyboard(lang),
            )
        return

    if kind == "await_onchain_topup_amount":
        try:
            amount = round(float(text.replace(",", ".")), 2)
            if amount < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Enter a valid amount of at least 1 USDT.")
            return
        network = str(ref)
        network_label = "BSC (BEP20)" if network == "bsc" else "Polygon"
        contract_warning = (
            "Verify that the USDT contract address ends in *97955*."
            if network == "bsc"
            else "Verify that the USDT contract address ends in *58e8f*."
        )
        PENDING[uid] = (
            "await_onchain_topup_txid",
            {"network": network, "amount": amount},
        )
        await update.message.reply_text(
            t(
                lang, "topup_onchain_instructions",
                network=network_label,
                amount=f"{amount:.2f}",
                address=USDT_EVM_ADDRESS,
                contract_warning=contract_warning,
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if kind == "await_onchain_topup_txid":
        result = await asyncio.to_thread(
            wallet_service.submit_onchain_topup,
            uid, text, float(ref["amount"]), str(ref["network"]),
        )
        if result["status"] != "manual_review":
            await update.message.reply_text(result.get("message") or "Invalid transaction ID.")
            return
        PENDING.pop(uid, None)
        network_label = "BSC (BEP20)" if result["network"] == "bsc" else "Polygon"
        await update.message.reply_text(
            t(
                lang, "topup_onchain_submitted",
                amount=f"{result['amount']:.2f}", network=network_label,
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.home_keyboard(lang, uid),
        )
        with contextlib.suppress(Exception):
            await context.bot.send_message(
                ADMIN_ID,
                "🔎 <b>Wallet top-up review</b>\n"
                f"Request: <b>#{result['id']}</b>\n"
                f"User: <code>{uid}</code>\n"
                f"Network: <b>{network_label}</b>\n"
                f"Claimed amount: <b>{result['amount']:.2f} USDT</b>\n"
                f"TXID: <code>{html.escape(result['txid'])}</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=kb.topup_review_keyboard(result["id"]),
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
        if text.strip() == "#":
            PENDING[uid] = ("adm_manual_stock", ref)
            await update.message.reply_text(
                "📦 *Stock manuel*\n\n"
                "Envoyez le nombre de comptes à afficher publiquement.\n"
                "Après chaque achat, ce stock diminuera automatiquement.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        try:
            items = inventory_service.parse_bulk_inventory(text)
            added = inventory_service.add_items(ref, items)
        except (RuntimeError, ValueError) as exc:
            await update.message.reply_text(f"⚠️ {exc}")
            return
        PENDING.pop(uid, None)
        stock = inventory_service.sync_offer_stock(ref)
        sent = 0
        if added:
            sent = await send_new_stock_broadcast(context, ref, added, stock)
        await update.message.reply_text(
            f"✅ {added} compte(s) ajouté(s) et chiffré(s).\n"
            f"📦 Stock affiché synchronisé dans le bot : {stock}\n"
            f"📣 Publicité privée envoyée à {sent} utilisateur(s).",
            reply_markup=admin.offer_admin_keyboard(ref),
        )
        return

    if kind == "adm_manual_stock" and uid == ADMIN_ID:
        try:
            stock = int(text.strip())
            if stock < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "⚠️ Envoyez un nombre entier valide supérieur ou égal à 0."
            )
            return
        db.update_offer(
            ref,
            stock=stock,
            manual_stock=True,
            unlimited_stock=False,
        )
        PENDING.pop(uid, None)
        sent = 0
        if stock > 0:
            sent = await send_new_stock_broadcast(context, ref, stock, stock)
        await update.message.reply_text(
            f"✅ Stock manuel activé : {stock}\n"
            "📦 Ce nombre est maintenant visible publiquement.\n"
            f"📣 Publicité privée envoyée à {sent} utilisateur(s).\n"
            "🤖 Après paiement, le bot vous demandera de répondre directement au client.",
            reply_markup=admin.offer_admin_keyboard(ref),
        )
        return

    if kind == "support":
        ticket = support_service.create_ticket(uid, text, category=str(ref or "other"))
        PENDING[uid] = ("ticket_message", ticket["id"])
        await send_ticket_conversation(update.message, lang, ticket)
        await support_bridge.send_client_text(
            context, ticket, update.effective_user, text,
        )
        await delete_customer_support_message(update.message)
        return

    if kind == "support_guided":
        category, order_id_text = str(ref).split("|", 1)
        order_id = int(order_id_text) or None
        if order_id:
            order = db.get_order(order_id)
            if not order or order.get("user_id") != uid:
                await update.message.reply_text(t(lang, "not_for_you"))
                return
        ticket = support_service.create_ticket(
            uid, text, category=category, order_id=order_id,
        )
        PENDING[uid] = ("ticket_message", ticket["id"])
        await send_ticket_conversation(update.message, lang, ticket)
        await support_bridge.send_client_text(
            context, ticket, update.effective_user, text,
        )
        await delete_customer_support_message(update.message)
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
        await send_ticket_conversation(update.message, lang, ticket)
        await support_bridge.send_client_text(
            context, ticket, update.effective_user, text,
        )
        await delete_customer_support_message(update.message)
        return

    if kind == "ticket_message":
        ticket = support_service.get_ticket(int(ref))
        if not ticket or ticket.get("user_id") != uid or ticket.get("status") == "closed":
            PENDING.pop(uid, None)
            await update.message.reply_text(t(lang, "ticket_unavailable"))
            return
        support_service.add_message(int(ref), uid, text, sender_type="client")
        await update.message.reply_text(
            f"Message sent to {support_bridge.ticket_reference(ref)}.",
            reply_markup=kb.ticket_conversation_keyboard(lang, ref),
        )
        await support_bridge.send_client_text(
            context,
            ticket,
            update.effective_user,
            text,
            event="Customer reply",
        )
        await delete_customer_support_message(update.message)
        return

    # --- Admin : livraison ---
    if kind == "adm_deliver" and uid == ADMIN_ID:
        await deliver_order(update, context, ref, text)
        PENDING.pop(uid, None)
        return


def is_otp_order(order):
    return bool(order and db.is_otp_service_name(order.get("service_name")))


async def begin_otp_order_questions(message, lang, order_id, uid):
    """Start or recover the paid OTP service/country questionnaire."""
    order = db.get_order(order_id)
    if not is_otp_order(order):
        return False
    workflow = str(order.get("otp_workflow_status") or "")
    if workflow == "sent_to_admin":
        return True
    pending = PENDING.get(uid)
    if workflow == "awaiting_country" and order.get("otp_service"):
        PENDING[uid] = (
            "otp_country",
            {"order_id": order_id, "service": order["otp_service"]},
        )
        if not pending or pending[0] != "otp_country":
            await message.reply_text(
                t(
                    lang,
                    "otp_ask_country",
                    service=escape_markdown(str(order["otp_service"])),
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        return True
    PENDING[uid] = ("otp_service", {"order_id": order_id})
    db.get_conn().orders.update_one(
        {"id": order_id},
        {"$set": {
            "otp_workflow_status": "awaiting_service",
            "updated_at": int(time.time()),
        }},
    )
    if not pending or pending[0] != "otp_service":
        await message.reply_text(
            t(lang, "otp_payment_confirmed_ask_service", oid=order_id),
            parse_mode=ParseMode.MARKDOWN,
        )
    return True

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
            else:
                await context.bot.send_message(
                    referrer_id,
                    premium_customer_text(
                        ref_lang,
                        "affiliate_payment_progress",
                        count=affiliate["valid_referrals"],
                        target=affiliate_service.REFERRAL_TARGET,
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
        paid_order = db.get_order(order_id)
        if is_otp_order(paid_order) and await begin_otp_order_questions(message, lang, order_id, uid):
            return
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
                                     parse_mode=ParseMode.HTML,
                                     reply_markup=kb.post_delivery_keyboard(lang, order_id))
        with contextlib.suppress(Exception):
            if result["status"] == "confirmed_no_delivery":
                await admin.notify_manual_delivery_request(context, paid_order)
            else:
                await admin.notify_new_order(context, paid_order)
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
            "not_found": "payment_not_found",
            "already_used": "payment_txid_used",
        }.get(error_code, "verify_failed")
        await message.reply_text(premium_customer_text(lang, error_key, oid=order_id),
                                 parse_mode=ParseMode.HTML)
        PENDING[uid] = ("await_txid", order_id)


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
                    for name in ("total", "binance_id"):
                        if name in format_kwargs:
                            format_kwargs[name] = f"<code>{format_kwargs[name]}</code>"
            with contextlib.suppress(KeyError, IndexError, ValueError):
                raw_value = raw_value.format(**format_kwargs)
    else:
        raw_value = t(lang, key, **kwargs)
    if key == "order_created" and not raw_value.startswith("[[HTML]]"):
        # Keep the payment values individually copyable in Telegram,
        # even when the admin's customized template uses plain placeholders.
        copyable_values = {
            name: str(kwargs[name])
            for name in ("total", "binance_id")
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


async def handle_ticket_attachment(update, context):
    """Create or continue a support ticket with a customer attachment."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return False
    pending = PENDING.get(user.id)
    if not pending or pending[0] not in {
        "support", "support_guided", "support_order", "ticket_message",
    }:
        return False

    label = support_bridge.media_label(message)
    caption = str(getattr(message, "caption", None) or "").strip()
    content = f"[{label}]" + (f" {caption}" if caption else "")
    kind, ref = pending
    is_new = kind != "ticket_message"

    if kind == "support":
        ticket = support_service.create_ticket(
            user.id, content, category=str(ref or "other"),
        )
    elif kind == "support_guided":
        category, order_id_text = str(ref).split("|", 1)
        order_id = int(order_id_text) or None
        if order_id:
            order = db.get_order(order_id)
            if not order or order.get("user_id") != user.id:
                await message.reply_text(t(lang_of(user.id), "not_for_you"))
                return True
        ticket = support_service.create_ticket(
            user.id, content, category=category, order_id=order_id,
        )
    elif kind == "support_order":
        ticket = support_service.create_ticket(
            user.id,
            content,
            category="delivery",
            order_id=int(ref),
            priority="high",
        )
    else:
        ticket = support_service.get_ticket(int(ref))
        if (
            not ticket
            or ticket.get("user_id") != user.id
            or ticket.get("status") == "closed"
        ):
            PENDING.pop(user.id, None)
            await message.reply_text(t(lang_of(user.id), "ticket_unavailable"))
            return True
        support_service.add_message(
            int(ref), user.id, content, sender_type="client",
        )

    ticket_id = int(ticket["id"])
    PENDING[user.id] = ("ticket_message", ticket_id)
    lang = lang_of(user.id)
    if is_new:
        await send_ticket_conversation(message, lang, ticket)
    else:
        await message.reply_text(
            f"Attachment sent to {support_bridge.ticket_reference(ticket_id)}.",
            reply_markup=kb.ticket_conversation_keyboard(lang, ticket_id),
        )
    await support_bridge.send_client_media(
        context,
        ticket,
        user,
        message,
        event="New support ticket" if is_new else "Customer attachment",
    )
    await delete_customer_support_message(message)
    return True


async def handle_pending_attachment(update, context):
    await handle_ticket_attachment(update, context)


async def handle_pending_photo(update, context):
    """Capture the advertising image during the guided offer creation flow."""
    if await handle_ticket_attachment(update, context):
        return
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

    if data.startswith("adm_topup_approve:"):
        topup_id = int(data.split(":", 1)[1])
        approved = wallet_service.approve_onchain_topup(topup_id, uid)
        if not approved:
            await q.edit_message_text("⚠️ This top-up was already processed or no longer exists.")
            return
        amount = int(approved["amount_cents"]) / 100
        customer_id = int(approved["user_id"])
        await q.edit_message_text(
            "✅ <b>Wallet top-up approved</b>\n"
            f"Request: <b>#{topup_id}</b>\n"
            f"User: <code>{customer_id}</code>\n"
            f"Credited: <b>{amount:.2f} USDT</b>",
            parse_mode=ParseMode.HTML,
        )
        with contextlib.suppress(Exception):
            await context.bot.send_message(
                customer_id,
                premium_customer_text(
                    lang_of(customer_id),
                    "topup_onchain_approved",
                    amount=f"{amount:.2f}",
                    balance=f"{float(approved['balance']):.2f}",
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.home_keyboard(lang_of(customer_id), customer_id),
            )
        return

    if data.startswith("adm_topup_reject:"):
        topup_id = int(data.split(":", 1)[1])
        rejected = wallet_service.reject_onchain_topup(topup_id, uid)
        if not rejected:
            await q.edit_message_text("⚠️ This top-up was already processed or no longer exists.")
            return
        customer_id = int(rejected["user_id"])
        await q.edit_message_text(
            "❌ <b>Wallet top-up rejected</b>\n"
            f"Request: <b>#{topup_id}</b>\n"
            f"User: <code>{customer_id}</code>",
            parse_mode=ParseMode.HTML,
        )
        with contextlib.suppress(Exception):
            await context.bot.send_message(
                customer_id,
                premium_customer_text(
                    lang_of(customer_id), "topup_onchain_rejected",
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.support_keyboard(lang_of(customer_id)),
            )
        return

    if data == "adm_user_activity":
        activity = db.user_activity_summary()
        await show_callback_screen(
            q,
            "👥 *Activité utilisateurs*\n\n"
            f"🟢 En ligne récemment : *{activity['online_now']}*\n"
            f"📅 Actifs aujourd’hui : *{activity['active_today']}*\n"
            f"👤 Total utilisateurs : *{activity['total_users']}*\n\n"
            "_« En ligne récemment » signifie actif sur le bot durant les 5 dernières minutes._",
            reply_markup=admin.user_activity_keyboard(),
        )
        return

    if data == "adm_maintenance_toggle":
        enabled = not db.shop_settings()["maintenance_enabled"]
        db.set_setting("maintenance_enabled", enabled)
        status = "ACTIVÉE 🔴" if enabled else "DÉSACTIVÉE 🟢"
        if enabled:
            settings = db.shop_settings()
            sent = await broadcast_maintenance_notice(
                context, settings["maintenance_message"],
            )
            detail = (
                "Tous les clients sont maintenant bloqués. Seul l'admin peut utiliser le bot.\n"
                f"📢 Notification envoyée à {sent} utilisateur(s)."
            )
        else:
            detail = "Le bot est de nouveau accessible à tous les clients."
        await show_callback_screen(
            q,
            "🛠️ *Panneau Admin*\n\n"
            f"Maintenance : *{status}*\n"
            f"{detail}",
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

    if data == "adm_broadcast_message":
        PENDING[uid] = ("adm_broadcast_message", 0)
        await q.message.reply_text(
            "📢 *Créer une annonce*\n\n"
            "Envoyez maintenant le message à publier à tous les utilisateurs.\n"
            "La mise en forme Telegram sera conservée.",
            parse_mode=ParseMode.MARKDOWN,
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
            "Pour une livraison manuelle, envoyez uniquement `#` : le bot vous demandera le stock public.\n\n"
            "Placez `#` au début de chaque nouveau compte. Le séparateur `#` sert uniquement au calcul du stock et ne sera jamais livré au client.\n"
            "Toutes les lignes suivantes appartiennent à ce compte jusqu'au prochain `#`.\n\n"
            "Exemple :\n"
            "`#Email: client1@example.com`\n"

            "`Password: secret1`\n"
            "`Instructions: profil A`\n\n"
            "`#Email: client2@example.com`\n"

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
            f"🧩 *{off['name']}*\n💵 Prix : {price}\n"
            f"📦 Stock : {'♾ Illimité' if off.get('unlimited_stock') else off['stock']}\n"
            f"🚚 Livraison : {'Admin' if off.get('manual_stock') else 'Automatique'}\n"
            f"📝 {off['note'] or '—'}",
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
    if data.startswith("adm_unlimited:"):
        oid = int(data.split(":")[1])
        off = db.get_offer(oid)
        enabled = not bool(off.get("unlimited_stock"))
        db.update_offer(oid, unlimited_stock=enabled, manual_stock=False)
        await q.edit_message_text(
            "✅ Stock illimité activé." if enabled else "✅ Stock illimité désactivé.",
            reply_markup=admin.offer_admin_keyboard(oid),
        )
        return
    if data.startswith("adm_flash_start:"):
        oid = int(data.split(":")[1])
        off = db.get_offer(oid)
        if not off or not off.get("active", 1) or off.get("price") is None:
            await q.answer("Offre indisponible.", show_alert=True)
            return
        PENDING[uid] = ("adm_flash_start", oid)
        await q.message.reply_text(
            f"⚡ *Lancer une vente flash — {off['name']}*\n\n"
            f"Prix actuel : *{float(off['price']):.2f} {CURRENCY}*\n"
            "Envoyez le nouveau prix et la durée en minutes.\n\n"
            "Exemple : `3 480` = 3 USDT pendant 8 heures.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if data.startswith("adm_flash_stop:"):
        oid = int(data.split(":")[1])
        off = db.stop_flash_sale(oid)
        await q.message.reply_text(
            f"⏹ Vente flash arrêtée.\n"
            f"Prix restauré : *{float(off.get('price') or 0):.2f} {CURRENCY}*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin.offer_admin_keyboard(oid),
        )
        return
    if data.startswith("adm_broadcast_offer:"):
        oid = int(data.split(":")[1])
        off = db.get_offer(oid)
        if not off or not off.get("active", 1):
            await q.answer("Offre indisponible.", show_alert=True)
            return
        stock = int(off.get("stock") or 0)
        if stock <= 0 and not off.get("unlimited_stock"):
            await q.answer("Aucun stock disponible à annoncer.", show_alert=True)
            return
        sent = await send_new_stock_broadcast(context, oid, None, stock)
        await q.message.reply_text(
            f"✅ Annonce envoyée à {sent} utilisateur(s).\n"
            f"💵 Prix actuel : {float(off.get('price') or 0):.2f} {CURRENCY}\n"
            f"📦 Stock annoncé : {'∞' if off.get('unlimited_stock') else stock}"
        )
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
            reply_markup=kb.post_delivery_keyboard(cl, order_id),
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
    # Report customer button clicks without consuming them, then apply global gates.
    app.add_handler(CallbackQueryHandler(notify_admin_interaction), group=-5)
    app.add_handler(MessageHandler(filters.ALL, block_maintenance_users), group=-4)
    app.add_handler(CallbackQueryHandler(block_maintenance_users), group=-4)
    app.add_handler(MessageHandler(filters.ALL, block_banned_users), group=-3)
    app.add_handler(CallbackQueryHandler(block_banned_users), group=-3)
    app.add_handler(MessageHandler(filters.ALL, block_non_channel_members), group=-2)
    app.add_handler(CallbackQueryHandler(block_non_channel_members), group=-2)
    app.add_handler(MessageHandler(
        filters.UpdateType.CHANNEL_POST
        & filters.Chat(SUPPORT_TICKET_CHANNEL_ID),
        support_bridge.handle_admin_channel_post,
    ))
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
    app.add_handler(MessageHandler(filters.ATTACHMENT, handle_pending_attachment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_menu))
    app.add_error_handler(on_error)
    return app


def main():
    app = build_app()
    log.info("HEAVENPREM bot démarré (long polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
