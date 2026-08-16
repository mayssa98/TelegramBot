"""Read-only JSON queries used by the administration dashboard."""

from __future__ import annotations

import re
from contextlib import suppress
from datetime import UTC, datetime, timedelta
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
    service_id = _first(params, "service_id")
    if service_id and service_id.isdigit():
        offer_ids = [row["id"] for row in db.get_conn().offers.find({"service_id": int(service_id)}, {"id": 1})]
        query["offer_id"] = {"$in": offer_ids}
    date_filter: dict[str, int] = {}
    for param_name, operator in (("date_from", "$gte"), ("date_to", "$lte")):
        raw = _first(params, param_name)
        if raw:
            with suppress(ValueError):
                date_filter[operator] = int(datetime.fromisoformat(raw).replace(tzinfo=UTC).timestamp())
    if date_filter:
        query["created_at"] = date_filter
    search = _first(params, "search")
    if search:
        field = _first(params, "search_field") or "all"
        pattern = {"$regex": re.escape(search), "$options": "i"}
        clauses: list[dict[str, Any]] = []
        if field in {"all", "name"}:
            clauses.extend(({"offer_name": pattern}, {"service_name": pattern}))
        if field in {"all", "txid"}:
            clauses.append({"txid": pattern})
        if search.isdigit() and field in {"all", "order_id"}:
            clauses.append({"id": int(search)})
        if search.isdigit() and field in {"all", "user_id"}:
            clauses.append({"user_id": int(search)})
        query["$or"] = clauses

    collection = db.get_conn().orders
    total = collection.count_documents(query)
    sort_field = "total_price" if _first(params, "sort") == "amount" else "created_at"
    sort_direction = 1 if _first(params, "direction") == "asc" else DESCENDING
    rows = collection.find(query).sort(sort_field, sort_direction).skip((page - 1) * per_page).limit(per_page)
    analytics_query = dict(query)
    analytics_query.pop("status", None)
    analytics = _order_analytics(collection, analytics_query)
    return {
        "items": [db._public(row) for row in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
        "analytics": analytics,
    }


def _order_analytics(collection: Any, query: dict[str, Any]) -> dict[str, Any]:
    """Build compact global metrics for the React orders dashboard."""
    now = datetime.now(UTC)
    start = (now - timedelta(days=6)).date()
    days = {
        (start + timedelta(days=offset)).isoformat(): {"count": 0, "revenue": 0.0}
        for offset in range(7)
    }
    statuses: dict[str, int] = {}
    revenue = 0.0
    paid_statuses = {"paid", "payment_confirmed", "delivered"}
    pending_statuses = {"pending_payment", "awaiting_verification", "manual_review", "preparing_delivery"}
    delivered = pending = 0

    for row in collection.find(query, {"status": 1, "total_price": 1, "created_at": 1}):
        status = str(row.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        amount = float(row.get("total_price") or 0)
        if status in paid_statuses:
            revenue += amount
        if status == "delivered":
            delivered += 1
        if status in pending_statuses:
            pending += 1

        created_at = row.get("created_at")
        try:
            created = (
                datetime.fromtimestamp(created_at, UTC)
                if isinstance(created_at, (int, float))
                else created_at.astimezone(UTC)
            )
            key = created.date().isoformat()
            if key in days:
                days[key]["count"] += 1
                if status in paid_statuses:
                    days[key]["revenue"] += amount
        except (AttributeError, OSError, OverflowError, TypeError, ValueError):
            continue

    total = sum(statuses.values())
    return {
        "total": total,
        "revenue": round(revenue, 2),
        "delivered": delivered,
        "pending": pending,
        "success_rate": round((delivered / total * 100) if total else 0, 1),
        "statuses": statuses,
        "daily": [
            {"date": key, "count": value["count"], "revenue": round(value["revenue"], 2)}
            for key, value in days.items()
        ],
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
    search = _first(params, "search")
    if search:
        field = _first(params, "search_field") or "all"
        pattern = {"$regex": re.escape(search), "$options": "i"}
        clauses: list[dict[str, Any]] = []
        if field in {"all", "category"}:
            clauses.append({"category": pattern})
        if field in {"all", "message"}:
            clauses.append({"message": pattern})
        if search.isdigit() and field in {"all", "ticket_id"}:
            clauses.append({"id": int(search)})
        if search.isdigit() and field in {"all", "user_id"}:
            clauses.append({"user_id": int(search)})
        query["$or"] = clauses

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


def list_inventory(params: dict[str, list[str]]) -> dict[str, Any]:
    """Return masked inventory references with server-side filters."""
    page = _bounded_int(_first(params, "page"), 1, 1, 100_000)
    per_page = _bounded_int(_first(params, "per_page"), 25, 1, 100)
    query: dict[str, Any] = {}
    offer_id = _first(params, "offer_id")
    if offer_id and offer_id.isdigit():
        query["offer_id"] = int(offer_id)
    status = _first(params, "status")
    if status:
        query["status"] = status
    search = _first(params, "search")
    if search:
        field = _first(params, "search_field") or "all"
        pattern = {"$regex": re.escape(search), "$options": "i"}
        clauses: list[dict[str, Any]] = []
        if field in {"all", "preview"}:
            clauses.append({"masked_preview": pattern})
        if search.isdigit() and field in {"all", "reference_id"}:
            clauses.append({"id": int(search)})
        if search.isdigit() and field in {"all", "product_id"}:
            clauses.append({"offer_id": int(search)})
        if search.isdigit() and field in {"all", "order_id"}:
            clauses.extend(({"reserved_order_id": int(search)}, {"delivered_order_id": int(search)}))
        query["$or"] = clauses

    collection = db.get_conn().inventory
    total = collection.count_documents(query)
    projection = {"payload": 0, "fingerprint": 0}
    rows = collection.find(query, projection).sort("created_at", DESCENDING).skip((page - 1) * per_page).limit(per_page)
    items = []
    for row in rows:
        item = db._public(row)
        item["reference_id"] = item.get("id")
        items.append(item)
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


def list_customers(params: dict[str, list[str]]) -> dict[str, Any]:
    """Return customer summaries with order and spending metrics."""
    page = _bounded_int(_first(params, "page"), 1, 1, 100_000)
    per_page = _bounded_int(_first(params, "per_page"), 25, 1, 100)
    query: dict[str, Any] = {}
    search = _first(params, "search")
    if search:
        field = _first(params, "search_field") or "all"
        pattern = {"$regex": re.escape(search), "$options": "i"}
        clauses: list[dict[str, Any]] = []
        if field in {"all", "username"}:
            clauses.append({"username": pattern})
        if field in {"all", "name"}:
            clauses.extend(({"first_name": pattern}, {"full_name": pattern}))
        if search.isdigit() and field in {"all", "telegram_id"}:
            clauses.append({"telegram_id": int(search)})
        query["$or"] = clauses
    collection = db.get_conn().users
    total = collection.count_documents(query)
    users = collection.find(query).sort("created_at", DESCENDING).skip((page - 1) * per_page).limit(per_page)
    return {
        "items": [_customer_summary(user) for user in users],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


def customer_detail(user_id: int) -> dict[str, Any] | None:
    """Return one customer with recent orders, tickets and referral metrics."""
    conn = db.get_conn()
    user = conn.users.find_one({"telegram_id": user_id})
    if not user:
        return None
    result = _customer_summary(user)
    result["orders"] = [db._public(row) for row in conn.orders.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(50)]
    result["tickets"] = [db._public(row) for row in conn.support_tickets.find({"user_id": user_id}).sort("updated_at", DESCENDING).limit(25)]
    result["referrals"] = conn.referrals.count_documents({"referrer_id": user_id})
    return result


def _customer_summary(user: dict[str, Any]) -> dict[str, Any]:
    conn = db.get_conn()
    user_id = user["telegram_id"]
    paid_filter = {"user_id": user_id, "status": {"$in": ["paid", "payment_confirmed", "delivered"]}}
    revenue = list(conn.orders.aggregate([
        {"$match": paid_filter},
        {"$group": {"_id": None, "total": {"$sum": "$total_price"}, "count": {"$sum": 1}}},
    ]))
    metrics = revenue[0] if revenue else {"total": 0, "count": 0}
    result = db._public(user)
    result.update({
        "order_count": conn.orders.count_documents({"user_id": user_id}),
        "paid_order_count": metrics["count"],
        "total_spent": round(float(metrics["total"]), 2),
        "referral_count": conn.referrals.count_documents({"referrer_id": user_id}),
        "wallet_balance": round(
            float((conn.wallets.find_one({"user_id": user_id}) or {}).get("balance_cents", 0)) / 100,
            2,
        ),
    })
    return result


def _first(params: dict[str, list[str]], key: str) -> str:
    values = params.get(key, [])
    return values[0].strip() if values else ""
