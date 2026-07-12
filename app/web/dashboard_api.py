"""Read-only JSON queries used by the administration dashboard."""

from __future__ import annotations

import re
from typing import Any

from pymongo import DESCENDING

import database as db


def _bounded_int(value: str | int | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def list_orders(params: dict[str, list[str]]) -> dict[str, Any]:
    """Return a filtered, paginated order collection."""
    page = _bounded_int(_first(params, "page"), 1, 1, 100_000)
    per_page = _bounded_int(_first(params, "per_page"), 25, 1, 100)
    query: dict[str, Any] = {}

    status = _first(params, "status")
    if status:
        query["status"] = status
    user_id = _first(params, "user_id")
    if user_id and user_id.isdigit():
        query["user_id"] = int(user_id)
    offer_id = _first(params, "offer_id")
    if offer_id and offer_id.isdigit():
        query["offer_id"] = int(offer_id)
    search = _first(params, "search")
    if search:
        clauses: list[dict[str, Any]] = [
            {"offer_name": {"$regex": re.escape(search), "$options": "i"}},
            {"service_name": {"$regex": re.escape(search), "$options": "i"}},
            {"txid": {"$regex": re.escape(search), "$options": "i"}},
        ]
        if search.isdigit():
            clauses.extend(({"id": int(search)}, {"user_id": int(search)}))
        query["$or"] = clauses

    collection = db.get_conn().orders
    total = collection.count_documents(query)
    rows = collection.find(query).sort("created_at", DESCENDING).skip((page - 1) * per_page).limit(per_page)
    return {
        "items": [db._public(row) for row in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


def list_tickets(params: dict[str, list[str]]) -> dict[str, Any]:
    """Return filtered, paginated support tickets."""
    page = _bounded_int(_first(params, "page"), 1, 1, 100_000)
    per_page = _bounded_int(_first(params, "per_page"), 25, 1, 100)
    query: dict[str, Any] = {}
    status = _first(params, "status")
    if status:
        query["status"] = status
    user_id = _first(params, "user_id")
    if user_id and user_id.isdigit():
        query["user_id"] = int(user_id)

    collection = db.get_conn().support_tickets
    total = collection.count_documents(query)
    rows = collection.find(query).sort("updated_at", DESCENDING).skip((page - 1) * per_page).limit(per_page)
    return {
        "items": [db._public(row) for row in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


def inventory_summary() -> list[dict[str, Any]]:
    """Return inventory counters per offer without exposing secret payloads."""
    conn = db.get_conn()
    pipeline = [
        {"$group": {"_id": {"offer_id": "$offer_id", "status": "$status"}, "count": {"$sum": 1}}},
        {"$sort": {"_id.offer_id": 1}},
    ]
    grouped: dict[int, dict[str, Any]] = {}
    for row in conn.inventory.aggregate(pipeline):
        offer_id = row["_id"]["offer_id"]
        entry = grouped.setdefault(offer_id, {"offer_id": offer_id, "available": 0, "reserved": 0, "delivered": 0, "disabled": 0})
        entry[row["_id"]["status"]] = row["count"]
    for entry in grouped.values():
        offer = conn.offers.find_one({"id": entry["offer_id"]}, {"name": 1})
        entry["offer_name"] = offer.get("name", "") if offer else ""
        entry["total"] = sum(entry.get(status, 0) for status in ("available", "reserved", "delivered", "disabled"))
    return list(grouped.values())


def _first(params: dict[str, list[str]], key: str) -> str:
    values = params.get(key, [])
    return values[0].strip() if values else ""
