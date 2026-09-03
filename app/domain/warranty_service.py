"""Product warranty display helpers."""
from __future__ import annotations

import re
from typing import Any


def format_warranty(days: Any, legacy_note: str = "", lang: str = "en") -> str:
    """Format warranty label: 0 days -> NW, >0 -> X days/j/يوم."""
    try:
        val = int(days) if days is not None else None
    except (TypeError, ValueError):
        val = None

    if val is not None:
        if val <= 0:
            return "NW"
        if lang == "fr":
            return f"{val} j"
        if lang == "ar":
            return f"{val} يوم"
        return f"{val} day{'s' if val != 1 else ''}"

    note = str(legacy_note or "").strip()
    if not note or note.upper() in {"NW", "NO WARRANTY", "SANS GARANTIE", "0"}:
        return "NW"
    match = re.search(r"(\d{1,3})\s*(?:d|day|days|j|jour|jours)", note, re.I)
    if match:
        d = int(match.group(1))
        if lang == "fr":
            return f"{d} j"
        if lang == "ar":
            return f"{d} يوم"
        return f"{d} day{'s' if d != 1 else ''}"
    return note


def offer_warranty_label(offer: dict[str, Any] | None, lang: str = "en") -> str:
    """Return the warranty text stored on an offer (0 -> NW)."""
    offer = offer or {}
    return format_warranty(offer.get("warranty_days"), offer.get("note", ""), lang)


def order_warranty_label(order: dict[str, Any] | None, lang: str = "en") -> str:
    """Return the warranty text stored on an order (0 -> NW)."""
    order = order or {}
    return format_warranty(order.get("warranty_days"), order.get("warranty", ""), lang)
