"""Product warranty display helpers."""
from __future__ import annotations

from typing import Any


def offer_warranty_label(offer: dict[str, Any] | None) -> str:
    """Return the warranty text stored on an offer."""
    offer = offer or {}
    return str(offer.get("note") or "").strip()


def order_warranty_label(order: dict[str, Any] | None) -> str:
    """Return the warranty text stored on an order."""
    order = order or {}
    return str(order.get("warranty") or "").strip()
