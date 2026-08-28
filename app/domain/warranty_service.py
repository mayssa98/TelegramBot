"""Structured product warranty options."""
from __future__ import annotations

import re
from typing import Any

WARRANTY_TYPES = {"NW", "FW"}
MIN_WARRANTY_DAYS = 1
MAX_WARRANTY_DAYS = 365


def infer_warranty(note: str) -> tuple[str, int]:
    """Infer structured values from legacy free-text warranties when possible."""
    text = str(note or "").strip()
    upper = text.upper()
    if re.search(r"\bNW\b", upper) or "NO WARRANTY" in upper or "SANS GARANTIE" in upper:
        return "NW", 0
    match = re.search(r"\b(\d{1,3})\s*(?:D|DAY|DAYS|J|JOUR|JOURS)\b", upper)
    if match:
        return "FW", max(MIN_WARRANTY_DAYS, min(MAX_WARRANTY_DAYS, int(match.group(1))))
    if re.search(r"\bFW\b", upper) or "FULL WARRANTY" in upper:
        return "FW", 30
    return "", 0


def normalize_warranty(warranty_type: str, warranty_days: Any = None) -> tuple[str, int]:
    """Validate a warranty type and its duration."""
    normalized_type = str(warranty_type or "").strip().upper()
    if normalized_type not in WARRANTY_TYPES:
        raise ValueError("Le type de garantie doit être NW ou FW.")
    if normalized_type == "NW":
        return "NW", 0
    try:
        days = int(warranty_days)
    except (TypeError, ValueError) as exc:
        raise ValueError("La durée FW doit être comprise entre 1 et 365 jours.") from exc
    if not MIN_WARRANTY_DAYS <= days <= MAX_WARRANTY_DAYS:
        raise ValueError("La durée FW doit être comprise entre 1 et 365 jours.")
    return "FW", days


def parse_warranty_input(value: str) -> tuple[str, int]:
    """Parse concise administrator input such as ``NW`` or ``FW 30``."""
    text = str(value or "").strip().upper().replace("|", " ").replace("-", " ")
    parts = text.split()
    if not parts:
        raise ValueError("Envoyez NW ou FW suivi du nombre de jours.")
    warranty_type = parts[0]
    days = parts[1] if len(parts) > 1 else None
    return normalize_warranty(warranty_type, days)


def warranty_label(
    warranty_type: str,
    warranty_days: Any = None,
    *,
    legacy_note: str = "",
) -> str:
    """Return the compact label displayed on product cards."""
    normalized_type = str(warranty_type or "").strip().upper()
    if normalized_type == "NW":
        return "NW · No warranty"
    if normalized_type == "FW":
        _type, days = normalize_warranty(normalized_type, warranty_days)
        return f"FW · {days} day{'s' if days != 1 else ''}"
    return str(legacy_note or "").strip()


def offer_warranty_label(offer: dict[str, Any] | None) -> str:
    offer = offer or {}
    return warranty_label(
        offer.get("warranty_type", ""),
        offer.get("warranty_days"),
        legacy_note=str(offer.get("note") or ""),
    )


def order_warranty_label(order: dict[str, Any] | None) -> str:
    """Return the fixed warranty option saved with an order."""
    order = order or {}
    return warranty_label(
        order.get("warranty_type", ""),
        order.get("warranty_days"),
        legacy_note=str(order.get("warranty") or ""),
    )
