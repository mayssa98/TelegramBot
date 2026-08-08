"""Bridge support tickets between customers and the private Telegram channel."""

from __future__ import annotations

import html
import re
from typing import Any

from telegram.constants import ParseMode

import database as db
import keyboards as kb
from app.domain import support_service
from config import ADMIN_ID, SUPPORT_TICKET_CHANNEL_ID

_TICKET_REFERENCE_RE = re.compile(
    r"^(?:/reply\s+)?(?:TKT-)?(?P<ticket_id>\d+)\b",
    re.IGNORECASE,
)


def ticket_reference(ticket_id: int) -> str:
    return f"TKT-{int(ticket_id):06d}"


def media_label(message: Any) -> str:
    for attribute, label in (
        ("photo", "Photo"),
        ("document", "Document"),
        ("video", "Video"),
        ("animation", "Animation"),
        ("audio", "Audio"),
        ("voice", "Voice message"),
        ("video_note", "Video note"),
        ("sticker", "Sticker"),
    ):
        if getattr(message, attribute, None):
            return label
    return "Attachment"


def _user_values(user: Any, user_id: int) -> tuple[str, str]:
    name = getattr(user, "full_name", None) or getattr(user, "first_name", None) or str(user_id)
    raw_username = getattr(user, "username", None) or ""
    return str(name), f"@{raw_username}" if raw_username else "Not provided"


def _channel_card(ticket: dict, user: Any, body: str, event: str) -> str:
    user_id = int(ticket["user_id"])
    name, username = _user_values(user, user_id)
    category = str(ticket.get("category") or "other").replace("_", " ").title()
    order_line = f"\n<b>Order:</b> #{int(ticket['order_id'])}" if ticket.get("order_id") else ""
    return (
        f"<b>{html.escape(event)} - {ticket_reference(ticket['id'])}</b>\n"
        f"<b>Category:</b> {html.escape(category)}\n"
        f'<b>Customer:</b> <a href="tg://user?id={user_id}">'
        f"{html.escape(name)}</a>\n"
        f"<b>Username:</b> {html.escape(username)}\n"
        f"<b>Telegram ID:</b> <code>{user_id}</code>"
        f"{order_line}\n\n"
        f"{html.escape(body[:2500])}\n\n"
        "<i>Reply to this post, or publish "
        f"<code>/reply {int(ticket['id'])} your message</code>.</i>"
    )


def _link_sent_message(ticket_id: int, sent: Any) -> None:
    message_id = getattr(sent, "message_id", None)
    if message_id:
        support_service.link_channel_message(ticket_id, int(message_id))


async def send_client_text(
    context,
    ticket: dict,
    user: Any,
    text: str,
    *,
    event: str = "New support ticket",
) -> None:
    sent = await context.bot.send_message(
        SUPPORT_TICKET_CHANNEL_ID,
        _channel_card(ticket, user, text, event),
        parse_mode=ParseMode.HTML,
    )
    _link_sent_message(ticket["id"], sent)


async def send_client_media(
    context,
    ticket: dict,
    user: Any,
    message: Any,
    *,
    event: str = "Customer attachment",
) -> None:
    caption = str(getattr(message, "caption", None) or "")
    summary = media_label(message)
    if caption:
        summary = f"{summary}: {caption}"
    header = await context.bot.send_message(
        SUPPORT_TICKET_CHANNEL_ID,
        _channel_card(ticket, user, summary, event),
        parse_mode=ParseMode.HTML,
    )
    _link_sent_message(ticket["id"], header)
    copied = await context.bot.copy_message(
        chat_id=SUPPORT_TICKET_CHANNEL_ID,
        from_chat_id=getattr(message, "chat_id", None) or message.chat.id,
        message_id=message.message_id,
    )
    _link_sent_message(ticket["id"], copied)


async def send_ticket_closed(context, ticket: dict, user: Any) -> None:
    sent = await context.bot.send_message(
        SUPPORT_TICKET_CHANNEL_ID,
        _channel_card(ticket, user, "Ticket closed by the customer.", "Ticket closed"),
        parse_mode=ParseMode.HTML,
    )
    _link_sent_message(ticket["id"], sent)


def _resolve_ticket(message: Any) -> tuple[dict | None, str]:
    reply = getattr(message, "reply_to_message", None)
    if reply and getattr(reply, "message_id", None):
        ticket = support_service.get_ticket_by_channel_message(reply.message_id)
        if ticket:
            return ticket, str(message.text or message.caption or "").strip()

    raw_text = str(message.text or message.caption or "").strip()
    match = _TICKET_REFERENCE_RE.match(raw_text)
    if not match:
        return None, raw_text
    ticket = support_service.get_ticket(int(match.group("ticket_id")))
    return ticket, raw_text[match.end() :].lstrip(" :-\n")


async def handle_admin_channel_post(update, context) -> bool:
    """Deliver a channel reply to the customer associated with that ticket post."""
    message = update.channel_post
    if not message or int(message.chat.id) != SUPPORT_TICKET_CHANNEL_ID:
        return False
    sender = getattr(message, "from_user", None)
    if sender and getattr(sender, "is_bot", False):
        return False

    ticket, content = _resolve_ticket(message)
    if not ticket or ticket.get("status") in {"closed", "resolved"}:
        return False

    has_media = any(
        getattr(message, attribute, None)
        for attribute in (
            "photo",
            "document",
            "video",
            "animation",
            "audio",
            "voice",
            "video_note",
            "sticker",
        )
    )
    if not content and not has_media:
        return False

    ticket_id = int(ticket["id"])
    user_id = int(ticket["user_id"])
    lang = db.get_user_lang(user_id) or "en"
    body = content or f"[{media_label(message)}]"
    await context.bot.send_message(
        user_id,
        (f"<b>Support reply - {ticket_reference(ticket_id)}</b>\n\n{html.escape(body[:2500])}"),
        parse_mode=ParseMode.HTML,
        reply_markup=kb.ticket_conversation_keyboard(lang, ticket_id),
    )
    if has_media:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SUPPORT_TICKET_CHANNEL_ID,
            message_id=message.message_id,
        )

    support_service.admin_reply(ticket_id, ADMIN_ID, body)
    support_service.link_channel_message(ticket_id, message.message_id)
    return True
