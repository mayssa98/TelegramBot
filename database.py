"""MongoDB persistence for users, catalogue, orders, and affiliate data."""
import base64
import hashlib
import os
import time
from datetime import UTC, datetime

from cryptography.fernet import Fernet
from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import INVENTORY_KEY, MONGODB_DB, MONGODB_URI

_client = None
_db = None
_schema_initialized = False
SCHEMA_VERSION = 5


def get_conn():
    """Return the configured MongoDB database, reusing the process-wide client."""
    global _client, _db
    if _db is None:
        if not MONGODB_URI:
            raise RuntimeError("HP_MONGODB_URI is required")
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
        _db = _client[MONGODB_DB]
    return _db


def _public(document):
    if document is None:
        return None
    result = dict(document)
    result.pop("_id", None)
    return result


def _next_id(sequence):
    row = get_conn().counters.find_one_and_update(
        {"_id": sequence}, {"$inc": {"value": 1}}, upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return row["value"]


def init_db():
    global _schema_initialized
    if _schema_initialized:
        return
    db = get_conn()
    db.command("ping")
    schema = db.schema_meta.find_one({"_id": "schema"}, {"version": 1})
    if schema and schema.get("version") == SCHEMA_VERSION:
        _schema_initialized = True
        return
    db.users.create_index("telegram_id", unique=True)
    db.services.create_index([("sort_order", ASCENDING), ("id", ASCENDING)])
    db.services.create_index("id", unique=True)
    db.offers.create_index("id", unique=True)
    db.offers.create_index([("service_id", ASCENDING), ("id", ASCENDING)])
    db.offers.create_index([("supplier_provider", ASCENDING), ("supplier_product_id", ASCENDING)])
    db.orders.create_index("id", unique=True)
    db.orders.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.orders.create_index("status")
    db.orders.create_index("txid", unique=True, partialFilterExpression={"txid": {"$gt": ""}})
    db.orders.create_index("expires_at")
    db.settings.create_index("key", unique=True)
    db.text_overrides.create_index([("key", ASCENDING), ("lang", ASCENDING)], unique=True)
    db.custom_buttons.create_index("id", unique=True)
    db.reseller_products.create_index(
        [("provider", ASCENDING), ("product_id", ASCENDING)], unique=True,
    )
    db.reseller_fulfillments.create_index(
        [("provider", ASCENDING), ("external_order_id", ASCENDING)], unique=True,
    )
    db.referrals.create_index("referred_id", unique=True)
    db.referrals.create_index("referrer_id")
    db.wallets.create_index("user_id", unique=True)
    db.wallet_topups.create_index("txid", unique=True)
    db.affiliate_rewards.create_index([("referrer_id", ASCENDING), ("milestone", ASCENDING)], unique=True)
    db.loyalty.create_index("user_id", unique=True)
    db.pending_states.create_index("user_id", unique=True)
    db.inventory.create_index([("offer_id", ASCENDING), ("status", ASCENDING)])
    db.inventory.create_index(
        [
            ("source_provider", ASCENDING),
            ("source_external_order_id", ASCENDING),
            ("source_item_index", ASCENDING),
        ],
        unique=True,
        sparse=True,
    )
    _backfill_inventory_ids(db)
    db.inventory.create_index("id", unique=True, sparse=True)
    fingerprint_index = db.inventory.index_information().get("fingerprint_1")
    if fingerprint_index:
        db.inventory.drop_index("fingerprint_1")
    db.inventory.create_index("reserved_order_id")
    db.processed_updates.create_index("created_at", expireAfterSeconds=604800)
    db.audit_events.create_index("created_at")
    db.interaction_events.create_index([("created_at", DESCENDING)])
    db.interaction_events.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.interaction_events.create_index([("interaction_type", ASCENDING), ("created_at", DESCENDING)])
    db.support_tickets.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    db.support_tickets.create_index("user_id")
    db.ticket_messages.create_index([("ticket_id", ASCENDING), ("created_at", ASCENDING)])
    if os.environ.get("HP_SEED_DEFAULT_CATALOG", "").strip().lower() in {"1", "true", "yes"}:
        _seed_catalog()
    db.schema_meta.update_one(
        {"_id": "schema"},
        {"$set": {"version": SCHEMA_VERSION, "updated_at": int(time.time())}},
        upsert=True,
    )
    _schema_initialized = True


def _backfill_inventory_ids(conn):
    """Assign stable numeric IDs to inventory created before the new schema."""
    for item in conn.inventory.find({"id": {"$exists": False}}, {"_id": 1}):
        conn.inventory.update_one(
            {"_id": item["_id"], "id": {"$exists": False}},
            {"$set": {"id": _next_id("inventory")}},
        )


def _seed_catalog():
    db = get_conn()
    if db.services.count_documents({}, limit=1):
        _repair_catalog_encoding(db)
        return
    catalog = [
        ("Canva", "🎨", [("Canva Pro 1m", .14, 113, ""), ("Canva Pro Head 1m", .86, 2, "")]),
        ("Capcut", "🎬", [("Capcut Pro 1m", 2.00, 24, "")]),
        ("Chatgpt", "🤖", [("Code Reedem Chatgpt GO 3m", .06, 14360, "")]),
        ("Discord Nitro", "🎮", [("Code Reedem Discord Nitro 1m", .29, 4, "")]),
        ("Gemini AI", "✨", [("Gemini Pro 12m [invit]", 1.43, 38, ""), ("Gemini Pro 12m [head]", 4.28, 50, "")]),
        ("Grok AI", "🧠", [("Supergrok 3M Sharing [garantie 25j]", 2.86, 5, "Garantie 25 jours"), ("Supergrok 3M Privat", 8.57, 28, "Gros volume >=25 pcs: 5.71$/pc"), ("Supergrok 6M Privat", 11.42, 100, "Gros volume: 10.85$/pc"), ("Supergrok 12M Privat", 17.14, 108, "Gros volume: 16.57$/pc")]),
        ("Manus AI", "🚀", [("Manus AI Pro 1m", 3.14, 14, "")]),
    ]
    extras = [("Adobe Creative Cloud", "🅰️", 5), ("Alight Motion", "📲", 46), ("Base44 AI", "🧩", 3), ("Duolingo", "🦉", 3), ("Emergent AI", "🌐", 1), ("Flux AI", "⚡", 1), ("Freebeat AI", "🎵", 19), ("Gamma AI", "📊", 16), ("Getcontac Premium", "📞", 3), ("Google Colab", "🐍", 36), ("Meitu", "📸", 1), ("Outlook Mail", "📧", 198), ("Perplexity AI", "🔍", 3), ("Picsart", "🖼️", 3), ("Reelshort", "📹", 1), ("Uncensored AI", "🔓", 3), ("Viu", "📺", 38), ("VPN", "🛡️", 2), ("Weshsop AI", "🛍️", 14)]
    catalog.extend((name, emoji, [("Offre standard", None, stock, "Prix à définir")]) for name, emoji, stock in extras)
    for order, (name, emoji, offers) in enumerate(catalog, 1):
        sid = _next_id("services")
        db.services.insert_one({"id": sid, "name": name, "emoji": emoji, "sort_order": order, "active": 1})
        for name_, price, stock, note in offers:
            db.offers.insert_one({"id": _next_id("offers"), "service_id": sid, "name": name_, "price": price, "stock": stock, "note": note, "active": 1})


def _repair_catalog_encoding(db):
    """Repair catalogue emojis previously seeded from a misencoded deployment."""
    emojis = {
        "Canva": "🎨", "Capcut": "🎬", "Chatgpt": "🤖",
        "Discord Nitro": "🎮", "Gemini AI": "✨", "Grok AI": "🧠",
        "Manus AI": "🚀", "Adobe Creative Cloud": "🅰️",
        "Alight Motion": "📲", "Base44 AI": "🧩", "Duolingo": "🦉",
        "Emergent AI": "🌐", "Flux AI": "⚡", "Freebeat AI": "🎵",
        "Gamma AI": "📊", "Getcontac Premium": "📞", "Google Colab": "🐍",
        "Meitu": "📸", "Outlook Mail": "📧", "Perplexity AI": "🔍",
        "Picsart": "🖼️", "Reelshort": "📹", "Uncensored AI": "🔓",
        "Viu": "📺", "VPN": "🛡️", "Weshsop AI": "🛍️",
    }
    for name, emoji in emojis.items():
        db.services.update_one({"name": name}, {"$set": {"emoji": emoji}})
    db.offers.update_many(
        {"note": {"$in": ["Prix Ã  définir", "Prix Ã  dÃ©finir"]}},
        {"$set": {"note": "Prix à définir"}},
    )


def upsert_user(telegram_id, username, first_name):
    now = int(time.time())
    result = get_conn().users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"username": username, "first_name": first_name}, "$setOnInsert": {"lang": "fr", "created_at": now}},
        upsert=True,
    )
    return result.upserted_id is not None


def get_user_lang(telegram_id):
    row = get_conn().users.find_one({"telegram_id": telegram_id}, {"lang": 1})
    return row.get("lang") if row else None


def set_user_lang(telegram_id, lang):
    get_conn().users.update_one({"telegram_id": telegram_id}, {"$set": {"lang": lang}})


def register_referral(referred_id, referrer_id, target=10, reward_cents=100):
    if referred_id == referrer_id or target < 1 or reward_cents < 0:
        return {"accepted": False, "rewarded": False, **affiliate_stats(referrer_id, target)}
    db = get_conn()
    if not db.users.find_one({"telegram_id": referrer_id}, {"_id": 1}):
        return {"accepted": False, "rewarded": False, **affiliate_stats(referrer_id, target)}
    try:
        db.referrals.insert_one({"referred_id": referred_id, "referrer_id": referrer_id, "created_at": int(time.time())})
    except DuplicateKeyError:
        return {"accepted": False, "rewarded": False, **affiliate_stats(referrer_id, target)}
    count = db.referrals.count_documents({"referrer_id": referrer_id})
    rewarded = False
    if count % target == 0:
        milestone = count // target
        try:
            db.affiliate_rewards.insert_one({"referrer_id": referrer_id, "milestone": milestone, "amount_cents": reward_cents, "created_at": int(time.time())})
            db.wallets.update_one({"user_id": referrer_id}, {"$inc": {"balance_cents": reward_cents}}, upsert=True)
            rewarded = True
        except DuplicateKeyError:
            pass
    return {"accepted": True, "rewarded": rewarded, **affiliate_stats(referrer_id, target)}


def affiliate_stats(user_id, target=10):
    db = get_conn()
    count = db.referrals.count_documents({"referrer_id": user_id})
    wallet = db.wallets.find_one({"user_id": user_id})
    return {"referrals": count, "balance_cents": wallet.get("balance_cents", 0) if wallet else 0, "progress": count % target, "remaining": target - (count % target) if count % target else target}


def list_services(active_only=True):
    query = {"active": 1} if active_only else {}
    return [_public(x) for x in get_conn().services.find(query).sort([("sort_order", ASCENDING), ("id", ASCENDING)])]


def list_services_with_stock(active_only=True):
    """Return services and stock totals with two queries instead of one per service."""
    conn = get_conn()
    services = [
        _public(item)
        for item in conn.services.find({"active": 1} if active_only else {}).sort(
            [("sort_order", ASCENDING), ("id", ASCENDING)]
        )
    ]
    totals = {
        row["_id"]: row["total"]
        for row in conn.offers.aggregate([
            {"$match": {"active": 1}},
            {"$group": {"_id": "$service_id", "total": {"$sum": "$stock"}}},
        ])
    }
    for service in services:
        has_unlimited = conn.offers.count_documents({
            "service_id": service["id"], "active": 1, "unlimited_stock": True,
        }) > 0
        service["unlimited_stock"] = has_unlimited
        service["total_stock"] = -1 if has_unlimited else totals.get(service["id"], 0)
    return services


def get_service(service_id):
    return _public(get_conn().services.find_one({"id": service_id}))


def list_offers(service_id, active_only=True):
    query = {"service_id": service_id}
    if active_only:
        query["active"] = 1
    return [_resolve_flash_sale(_public(x)) for x in get_conn().offers.find(query).sort("id", ASCENDING)]


def get_offer(offer_id):
    return _resolve_flash_sale(_public(get_conn().offers.find_one({"id": offer_id})))


def _resolve_flash_sale(offer):
    """Restore the regular price when a flash sale has expired."""
    if not offer or not offer.get("flash_sale_active"):
        return offer
    if int(offer.get("flash_sale_ends_at") or 0) > int(time.time()):
        return offer
    original_price = offer.get("flash_sale_original_price")
    get_conn().offers.update_one(
        {"id": offer["id"], "flash_sale_active": True},
        {
            "$set": {"price": original_price, "flash_sale_active": False},
            "$unset": {
                "flash_sale_price": "",
                "flash_sale_original_price": "",
                "flash_sale_ends_at": "",
            },
        },
    )
    offer["price"] = original_price
    offer["flash_sale_active"] = False
    offer.pop("flash_sale_price", None)
    offer.pop("flash_sale_original_price", None)
    offer.pop("flash_sale_ends_at", None)
    return offer


def start_flash_sale(offer_id, sale_price, duration_minutes):
    offer = get_offer(int(offer_id))
    sale_price = round(float(sale_price), 2)
    duration_minutes = int(duration_minutes)
    if not offer or offer.get("price") is None:
        raise ValueError("Offre introuvable ou sans prix.")
    if sale_price < 0 or sale_price >= float(offer["price"]):
        raise ValueError("Le prix flash doit être inférieur au prix actuel.")
    if duration_minutes < 1 or duration_minutes > 10080:
        raise ValueError("La durée doit être comprise entre 1 minute et 7 jours.")
    ends_at = int(time.time()) + duration_minutes * 60
    get_conn().offers.update_one(
        {"id": int(offer_id)},
        {"$set": {
            "flash_sale_active": True,
            "flash_sale_original_price": float(offer["price"]),
            "flash_sale_price": sale_price,
            "flash_sale_ends_at": ends_at,
            "price": sale_price,
        }},
    )
    return get_offer(int(offer_id))


def stop_flash_sale(offer_id):
    offer = get_offer(int(offer_id))
    if not offer or not offer.get("flash_sale_active"):
        return offer
    original_price = offer.get("flash_sale_original_price")
    get_conn().offers.update_one(
        {"id": int(offer_id)},
        {
            "$set": {"price": original_price, "flash_sale_active": False},
            "$unset": {
                "flash_sale_price": "",
                "flash_sale_original_price": "",
                "flash_sale_ends_at": "",
            },
        },
    )
    return get_offer(int(offer_id))


def offer_has_stock(offer, qty=1):
    """Return whether an offer can fulfill a quantity, including unlimited offers."""
    if not offer or int(qty or 0) < 1:
        return False
    return bool(offer.get("unlimited_stock")) or int(offer.get("stock") or 0) >= int(qty)


def service_total_stock(service_id):
    result = list(get_conn().offers.aggregate([{"$match": {"service_id": service_id, "active": 1}}, {"$group": {"_id": None, "total": {"$sum": "$stock"}}}]))
    return result[0]["total"] if result else 0


def update_offer(
    offer_id,
    price=None,
    stock=None,
    name=None,
    note=None,
    active=None,
    description=None,
    currency=None,
    sort_order=None,
    auto_delivery=None,
    low_stock_threshold=None,
    delivery_delay=None,
    custom_emoji_id=None,
    photo_file_id=None,
    instructions=None,
    unlimited_stock=None,
    manual_stock=None,
    supplier_provider=None,
    supplier_product_id=None,
):
    values = {
        key: value
        for key, value in {
            "price": price,
            "stock": stock,
            "name": name,
            "note": note,
            "active": active,
            "description": description,
            "currency": currency,
            "sort_order": sort_order,
            "auto_delivery": auto_delivery,
            "low_stock_threshold": low_stock_threshold,
            "delivery_delay": delivery_delay,
            "custom_emoji_id": custom_emoji_id,
            "photo_file_id": photo_file_id,
            "instructions": instructions,
            "unlimited_stock": unlimited_stock,
            "manual_stock": manual_stock,
            "supplier_provider": supplier_provider,
            "supplier_product_id": supplier_product_id,
        }.items()
        if value is not None
    }
    if values:
        get_conn().offers.update_one({"id": offer_id}, {"$set": values})


def add_service(name, emoji="", custom_emoji_id=""):
    db = get_conn()
    last = db.services.find_one(sort=[("sort_order", DESCENDING)])
    sid = _next_id("services")
    db.services.insert_one({
        "id": sid,
        "name": name,
        "emoji": emoji,
        "custom_emoji_id": custom_emoji_id,
        "sort_order": (last or {}).get("sort_order", 0) + 1,
        "active": 1,
    })
    return sid


def update_service(service_id, name=None, emoji=None, active=None, custom_emoji_id=None):
    values = {
        k: v
        for k, v in {
            "name": name,
            "emoji": emoji,
            "active": active,
            "custom_emoji_id": custom_emoji_id,
        }.items()
        if v is not None
    }
    return bool(values and get_conn().services.update_one({"id": service_id}, {"$set": values}).matched_count)


def archive_service(service_id):
    db = get_conn()
    db.services.update_one({"id": service_id}, {"$set": {"active": 0}})
    db.offers.update_many({"service_id": service_id}, {"$set": {"active": 0}})


def archive_offer(offer_id):
    return update_offer(offer_id, active=0)


def add_offer(
    service_id,
    name,
    price,
    stock,
    note="",
    description="",
    currency="USDT",
    auto_delivery=True,
    low_stock_threshold=5,
    delivery_delay="Instantané après confirmation",
    custom_emoji_id="",
    photo_file_id="",
    instructions="",
    unlimited_stock=False,
    manual_stock=False,
    supplier_provider="",
    supplier_product_id="",
):
    oid = _next_id("offers")
    last = get_conn().offers.find_one({"service_id": service_id}, sort=[("sort_order", DESCENDING)])
    get_conn().offers.insert_one({
        "id": oid,
        "service_id": service_id,
        "name": name,
        "description": description,
        "price": price,
        "currency": currency,
        "stock": stock,
        "note": note,
        "auto_delivery": bool(auto_delivery),
        "low_stock_threshold": int(low_stock_threshold),
        "delivery_delay": delivery_delay,
        "custom_emoji_id": custom_emoji_id,
        "photo_file_id": photo_file_id,
        "instructions": instructions,
        "unlimited_stock": bool(unlimited_stock),
        "manual_stock": bool(manual_stock),
        "supplier_provider": str(supplier_provider or ""),
        "supplier_product_id": str(supplier_product_id or ""),
        "sort_order": (last or {}).get("sort_order", 0) + 1,
        "active": 1,
    })
    return oid


def offer_sold_count(offer_id):
    """Return the quantity sold from confirmed, paid, or delivered orders."""
    pipeline = [
        {"$match": {
            "offer_id": offer_id,
            "status": {"$in": ["paid", "payment_confirmed", "delivered"]},
        }},
        {"$group": {"_id": None, "total": {"$sum": "$qty"}}},
    ]
    result = list(get_conn().orders.aggregate(pipeline))
    return int(result[0]["total"]) if result else 0


def duplicate_offer(offer_id):
    """Duplicate an offer without copying its inventory."""
    source = get_conn().offers.find_one({"id": offer_id})
    if not source:
        return None
    return add_offer(
        source["service_id"], f"{source['name']} (copie)", source.get("price"), 0,
        source.get("note", ""), description=source.get("description", ""),
        currency=source.get("currency", "USDT"), auto_delivery=source.get("auto_delivery", True),
        low_stock_threshold=source.get("low_stock_threshold", 5),
        delivery_delay=source.get("delivery_delay", ""),
        unlimited_stock=source.get("unlimited_stock", False),
        manual_stock=source.get("manual_stock", False),
    )


def decrement_stock(offer_id, qty):
    get_conn().offers.update_one({"id": offer_id}, [{"$set": {"stock": {"$max": [0, {"$subtract": ["$stock", qty]}]}}}])


def mark_order_paid(order_id, verify_method):
    db = get_conn()
    order = db.orders.find_one({"id": order_id})
    if not order or order.get("status") in ("paid", "payment_confirmed", "delivered"):
        return bool(order)
    if order.get("status") not in (
        "awaiting_verification",
        "pending_payment",
        "verification_failed",
        "manual_review",
    ):
        return False
    offer = db.offers.find_one({"id": order.get("offer_id")}) if order.get("offer_id") else None
    stock_decremented = False
    if offer and not offer.get("unlimited_stock"):
        stock = db.offers.update_one(
            {"id": order["offer_id"], "stock": {"$gte": order["qty"]}},
            {"$inc": {"stock": -order["qty"]}},
        )
        if stock.modified_count != 1:
            return False
        stock_decremented = True
    paid = db.orders.update_one(
        {"id": order_id, "status": order["status"]},
        {
            "$set": {
                "status": "payment_confirmed",
                "verify_method": verify_method,
                "paid_at": int(time.time()),
                "updated_at": int(time.time()),
            }
        },
    )
    if paid.modified_count != 1 and stock_decremented:
        db.offers.update_one({"id": order["offer_id"]}, {"$inc": {"stock": order["qty"]}})
    return paid.modified_count == 1


def create_order(user_id, offer, qty):
    now = int(time.time())
    unit = offer.get("price") or 0
    service = get_service(offer["service_id"])
    oid = _next_id("orders")
    get_conn().orders.insert_one({"id": oid, "user_id": user_id, "offer_id": offer["id"], "service_name": service["name"] if service else "", "offer_name": offer["name"], "qty": qty, "unit_price": unit, "total_price": round(unit * qty, 2), "status": "pending_payment", "txid": "", "verify_method": "", "delivery_text": "", "created_at": now, "updated_at": now})
    return oid


def get_order(order_id):
    return _public(get_conn().orders.find_one({"id": order_id}))


def update_order(order_id, **kwargs):
    if not kwargs:
        return
    allowed = {"status", "txid", "verify_method", "delivery_text", "updated_at"}
    kwargs["updated_at"] = int(time.time())
    unknown = set(kwargs) - allowed
    if unknown:
        raise ValueError(f"Champs de commande interdits: {sorted(unknown)}")
    get_conn().orders.update_one({"id": order_id}, {"$set": kwargs})


def claim_order_channel_announcement(order_id):
    """Atomically reserve the one public purchase announcement for an order."""
    result = get_conn().orders.update_one(
        {"id": int(order_id), "channel_sale_announced": {"$ne": True}},
        {"$set": {"channel_sale_announced": True, "updated_at": int(time.time())}},
    )
    return result.modified_count == 1


def release_order_channel_announcement(order_id):
    """Allow a later retry when Telegram could not publish the announcement."""
    get_conn().orders.update_one(
        {"id": int(order_id)},
        {"$set": {"channel_sale_announced": False, "updated_at": int(time.time())}},
    )

def list_orders(status=None, limit=30):
    query = {"status": status} if status else {}
    return [_public(x) for x in get_conn().orders.find(query).sort("id", DESCENDING).limit(limit)]


def list_user_orders(user_id, limit=15):
    return [_public(x) for x in get_conn().orders.find({"user_id": user_id}).sort("id", DESCENDING).limit(limit)]


def user_account_summary(user_id):
    db = get_conn()
    user = _public(db.users.find_one({"telegram_id": user_id})) or {"telegram_id": user_id}
    orders = list_user_orders(user_id, limit=25)
    paid_statuses = {"paid", "payment_confirmed", "delivered"}
    paid = list(db.orders.find({"user_id": user_id, "status": {"$in": list(paid_statuses)}}))
    user.update({
        "orders": orders,
        "order_count": db.orders.count_documents({"user_id": user_id}),
        "paid_count": db.orders.count_documents({"user_id": user_id, "status": {"$in": list(paid_statuses)}}),
        "total_paid": round(sum(float(x.get("total_price") or 0) for x in paid), 2),
    })
    return user


def get_setting(key, default=None):
    row = get_conn().settings.find_one({"key": key})
    return row.get("value", default) if row else default


def set_setting(key, value):
    get_conn().settings.update_one({"key": key}, {"$set": {"value": str(value)}}, upsert=True)


def get_text_override(key, lang):
    row = get_conn().text_overrides.find_one({"key": str(key), "lang": str(lang)})
    return row.get("text") if row else None


def get_text_override_icon(key, lang):
    row = get_conn().text_overrides.find_one({"key": str(key), "lang": str(lang)})
    return row.get("custom_emoji_id", "") if row else ""


def set_text_override(key, lang, text, custom_emoji_id=""):
    get_conn().text_overrides.update_one(
        {"key": str(key), "lang": str(lang)},
        {"$set": {
            "text": str(text), "custom_emoji_id": str(custom_emoji_id or ""),
            "updated_at": int(time.time()),
        }},
        upsert=True,
    )


def list_text_overrides():
    return [_public(row) for row in get_conn().text_overrides.find().sort([("key", ASCENDING), ("lang", ASCENDING)])]


def add_custom_button(label_fr, label_en, label_ar, url):
    button_id = _next_id("custom_buttons")
    get_conn().custom_buttons.insert_one({
        "id": button_id, "label_fr": label_fr, "label_en": label_en,
        "label_ar": label_ar, "url": url, "active": 1,
    })
    return button_id


def list_custom_buttons(active_only=True):
    query = {"active": 1} if active_only else {}
    return [_public(row) for row in get_conn().custom_buttons.find(query).sort("id", ASCENDING)]


def delete_custom_button(button_id):
    return bool(get_conn().custom_buttons.delete_one({"id": int(button_id)}).deleted_count)


def list_reseller_product_configs(provider="mailreader"):
    """Return administrator selections for one external product supplier."""
    return [
        _public(row)
        for row in get_conn().reseller_products.find(
            {"provider": str(provider)}
        ).sort("name", ASCENDING)
    ]


def save_reseller_product_config(
    provider,
    product_id,
    *,
    name,
    wholesale_price,
    currency,
    retail_price,
    enabled,
    service_id=None,
    local_offer_id=None,
    display_name="",
    service_name="",
    service_emoji="",
    description="",
    warranty="Produit API MailReader",
    delivery_delay="Instantané après confirmation",
    sort_order=0,
    low_stock_threshold=5,
):
    """Persist retail pricing and visibility without storing supplier secrets."""
    now = int(time.time())
    get_conn().reseller_products.update_one(
        {"provider": str(provider), "product_id": str(product_id)},
        {
            "$set": {
                "name": str(name)[:200],
                "wholesale_price": float(wholesale_price),
                "currency": str(currency or "USDT")[:12],
                "retail_price": float(retail_price),
                "enabled": bool(enabled),
                "service_id": int(service_id) if service_id is not None else None,
                "local_offer_id": int(local_offer_id) if local_offer_id is not None else None,
                "display_name": str(display_name or name)[:200],
                "service_name": str(service_name or "")[:100],
                "service_emoji": str(service_emoji or "")[:16],
                "description": str(description or "")[:2000],
                "warranty": str(warranty or "")[:250],
                "delivery_delay": str(delivery_delay or "")[:120],
                "sort_order": max(0, int(sort_order or 0)),
                "low_stock_threshold": max(0, int(low_stock_threshold or 0)),
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return _public(
        get_conn().reseller_products.find_one(
            {"provider": str(provider), "product_id": str(product_id)}
        )
    )


def shop_settings():
    """Return typed, administrator-editable shop settings."""
    from config import (
        AFFILIATE_DAILY_CAP,
        AFFILIATE_FIVE_REWARD_CENTS,
        BINANCE_PAY_ID,
        LOW_STOCK_THRESHOLD,
        ORDER_EXPIRY_SECONDS,
        SHOP_NAME,
    )

    defaults = {
        "shop_name": SHOP_NAME,
        "currency": "USDT",
        "payment_recipient": BINANCE_PAY_ID,
        "order_expiry_seconds": ORDER_EXPIRY_SECONDS,
        "low_stock_threshold": LOW_STOCK_THRESHOLD,
        "affiliate_enabled": True,
        "affiliate_target": AFFILIATE_DAILY_CAP,
        "affiliate_reward_cents": AFFILIATE_FIVE_REWARD_CENTS,
        "maintenance_enabled": False,
        "maintenance_message": "La boutique est temporairement en maintenance.",
        "welcome_message": "",
        "help_message": "",
        "terms_message": "",
        "privacy_message": "",
        "active_languages": "en",
    }
    rows = {row["key"]: row.get("value") for row in get_conn().settings.find({"key": {"$in": list(defaults)}})}
    result = defaults | rows
    for key in ("order_expiry_seconds", "low_stock_threshold", "affiliate_target", "affiliate_reward_cents"):
        result[key] = int(result[key])
    for key in ("affiliate_enabled", "maintenance_enabled"):
        result[key] = str(result[key]).lower() in {"1", "true", "yes", "on"}
    return result


def get_pending_state(user_id):
    row = get_conn().pending_states.find_one({"user_id": user_id})
    return (row["kind"], row["ref"]) if row else None


def set_pending_state(user_id, state):
    kind, ref = state
    get_conn().pending_states.update_one(
        {"user_id": user_id},
        {"$set": {"kind": kind, "ref": ref, "updated_at": int(time.time())}},
        upsert=True,
    )


def pop_pending_state(user_id, default=None):
    row = get_conn().pending_states.find_one_and_delete({"user_id": user_id})
    return (row["kind"], row["ref"]) if row else default


def claim_update(update_id):
    """Return False when Telegram retries an update already being processed."""
    try:
        get_conn().processed_updates.insert_one({"_id": update_id, "created_at": datetime.now(UTC)})
        return True
    except DuplicateKeyError:
        return False


def release_update(update_id):
    get_conn().processed_updates.delete_one({"_id": update_id})


def _fernet():
    key = INVENTORY_KEY
    if not key:
        secret = (
            os.environ.get("HP_BOT_TOKEN", "")
            or os.environ.get("HP_WEBHOOK_SECRET", "")
            or os.environ.get("HP_DASHBOARD_PASSWORD", "")
            or os.environ.get("HP_MONGODB_URI", "")
        ).strip()
        if not secret:
            raise RuntimeError("HP_INVENTORY_KEY or another deployment secret is required for automatic inventory")
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()).decode()
    return Fernet(key.encode())


def add_inventory_items(offer_id, items):
    """Legacy importer that stores every non-empty account, including duplicates."""
    db = get_conn()
    cipher = _fernet()
    added = 0
    for value in (x.strip() for x in items):
        if not value:
            continue
        db.inventory.insert_one({
            "offer_id": offer_id,
            "payload": cipher.encrypt(value.encode()).decode(),
            "status": "available",
            "created_at": int(time.time()),
        })
        added += 1
    if added:
        db.offers.update_one({"id": offer_id}, {"$inc": {"stock": added}})
    return added

def inventory_stats(offer_id):
    db = get_conn()
    return {status: db.inventory.count_documents({"offer_id": offer_id, "status": status}) for status in ("available", "sold")}


def fulfill_order(order_id):
    """Atomically claim encrypted stock and return decrypted delivery values."""
    db = get_conn()
    order = db.orders.find_one({"id": order_id, "status": "paid"})
    if not order or not order.get("offer_id"):
        return None
    claimed = []
    for _ in range(order.get("qty", 1)):
        item = db.inventory.find_one_and_update(
            {"offer_id": order["offer_id"], "status": "available"},
            {"$set": {"status": "reserved", "order_id": order_id, "reserved_at": int(time.time())}},
            return_document=ReturnDocument.AFTER,
        )
        if not item:
            db.inventory.update_many({"order_id": order_id, "status": "reserved"}, {"$set": {"status": "available"}, "$unset": {"order_id": "", "reserved_at": ""}})
            return None
        claimed.append(item)
    values = [_fernet().decrypt(x["payload"].encode()).decode() for x in claimed]
    db.inventory.update_many({"order_id": order_id, "status": "reserved"}, {"$set": {"status": "sold", "sold_at": int(time.time())}})
    db.orders.update_one({"id": order_id, "status": "paid"}, {"$set": {"status": "delivered", "delivery_text": "[encrypted automatic delivery]", "updated_at": int(time.time())}})
    return values


def audit_event(action, actor_id=None, details=None):
    get_conn().audit_events.insert_one({"action": action, "actor_id": actor_id, "details": details or {}, "created_at": datetime.now(UTC)})


def log_interaction(
    user_id,
    *,
    first_name="",
    full_name="",
    username="",
    interaction_type="message",
    action="",
    content="",
    screen="",
):
    """Persist one customer interaction for live dashboard analytics."""
    now = int(time.time())
    event = {
        "user_id": int(user_id),
        "first_name": str(first_name or "")[:200],
        "full_name": str(full_name or first_name or "")[:300],
        "username": str(username or "")[:100],
        "interaction_type": str(interaction_type or "message")[:50],
        "action": str(action or "")[:500],
        "content": str(content or "")[:2000],
        "screen": str(screen or "")[:1000],
        "created_at": now,
    }
    get_conn().interaction_events.insert_one(event)
    get_conn().users.update_one(
        {"telegram_id": int(user_id)},
        {
            "$set": {"last_active_at": now},
            "$inc": {"interaction_count": 1},
        },
    )
    return _public(event)


def interaction_analytics(days=30, limit=1000):
    """Return interaction KPIs, daily chart points, and detailed recent events."""
    conn = get_conn()
    now = int(time.time())
    today_start = now - (now % 86400)
    start = today_start - (max(1, int(days)) - 1) * 86400
    live_since = now - 300
    events = [
        _public(row)
        for row in conn.interaction_events.find(
            {"created_at": {"$gte": start}}
        ).sort("created_at", DESCENDING).limit(max(1, int(limit)))
    ]
    daily_counts = {}
    type_counts = {}
    active_today = set()
    live_users = set()
    for event in conn.interaction_events.find(
        {"created_at": {"$gte": start}},
        {"created_at": 1, "user_id": 1, "interaction_type": 1},
    ):
        timestamp = int(event.get("created_at") or 0)
        day = datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d")
        daily_counts[day] = daily_counts.get(day, 0) + 1
        kind = str(event.get("interaction_type") or "other")
        type_counts[kind] = type_counts.get(kind, 0) + 1
        if timestamp >= today_start:
            active_today.add(event.get("user_id"))
        if timestamp >= live_since:
            live_users.add(event.get("user_id"))
    daily = []
    for offset in range(max(1, int(days))):
        day_timestamp = start + offset * 86400
        day = datetime.fromtimestamp(day_timestamp, UTC).strftime("%Y-%m-%d")
        daily.append({"date": day, "count": daily_counts.get(day, 0)})
    return {
        "summary": {
            "total": conn.interaction_events.count_documents({}),
            "today": conn.interaction_events.count_documents(
                {"created_at": {"$gte": today_start}}
            ),
            "active_today": len(active_today),
            "live_users": len(live_users),
            "button_clicks": type_counts.get("button", 0),
            "messages": type_counts.get("message", 0) + type_counts.get("command", 0),
        },
        "daily": daily,
        "types": type_counts,
        "events": events,
    }


def user_activity_summary():
    """Return bot activity counts; 'online' means active within five minutes."""
    analytics = interaction_analytics(days=30, limit=1)["summary"]
    return {
        "online_now": analytics["live_users"],
        "active_today": analytics["active_today"],
        "total_users": get_conn().users.count_documents({}),
    }


def dashboard_summary():
    """Legacy wrapper — kept for backward compatibility."""
    data = dashboard_data()
    return data.get("summary", {})


def dashboard_data():
    """Comprehensive dashboard data for the admin panel."""
    db = get_conn()
    now = int(time.time())
    today_start = now - (now % 86400)
    yesterday_start = today_start - 86400
    week_ago = now - 7 * 86400
    month_ago = now - 30 * 86400
    prev_week_start = week_ago - 7 * 86400

    # --- Users ---
    total_users = db.users.count_documents({})
    new_users_today = db.users.count_documents({"created_at": {"$gte": today_start}})
    new_users_7d = db.users.count_documents({"created_at": {"$gte": week_ago}})
    new_users_prev_7d = db.users.count_documents({"created_at": {"$gte": prev_week_start, "$lt": week_ago}})

    # --- Orders ---
    total_orders = db.orders.count_documents({})
    orders_today = db.orders.count_documents({"created_at": {"$gte": today_start}})
    orders_yesterday = db.orders.count_documents({"created_at": {"$gte": yesterday_start, "$lt": today_start}})
    pending_orders = db.orders.count_documents({"status": {"$in": ["pending_payment", "awaiting_verification", "manual_review"]}})

    paid_statuses = ["paid", "payment_confirmed", "delivered"]
    paid_orders = db.orders.count_documents({"status": {"$in": paid_statuses}})
    delivered_orders = db.orders.count_documents({"status": "delivered"})

    # --- Revenue ---
    def _revenue(match_filter):
        result = list(db.orders.aggregate([
            {"$match": match_filter},
            {"$group": {"_id": None, "total": {"$sum": "$total_price"}}},
        ]))
        return round(result[0]["total"], 2) if result else 0.0

    revenue_today = _revenue({"status": {"$in": paid_statuses}, "created_at": {"$gte": today_start}})
    revenue_yesterday = _revenue({"status": {"$in": paid_statuses}, "created_at": {"$gte": yesterday_start, "$lt": today_start}})
    revenue_7d = _revenue({"status": {"$in": paid_statuses}, "created_at": {"$gte": week_ago}})
    revenue_30d = _revenue({"status": {"$in": paid_statuses}, "created_at": {"$gte": month_ago}})
    revenue_prev_7d = _revenue({"status": {"$in": paid_statuses}, "created_at": {"$gte": prev_week_start, "$lt": week_ago}})

    # Conversion rate
    conversion_rate = round((paid_orders / total_orders * 100) if total_orders else 0, 1)

    # --- Tickets ---
    open_tickets = db.support_tickets.count_documents({"status": {"$nin": ["closed", "resolved"]}})

    # --- Inventory & stock ---
    available_inventory = db.inventory.count_documents({"status": "available"})

    # Low stock offers
    from config import LOW_STOCK_THRESHOLD
    low_stock_offers = list(db.offers.find(
        {"active": 1, "stock": {"$lte": LOW_STOCK_THRESHOLD, "$gt": 0}},
        {"id": 1, "name": 1, "stock": 1, "service_id": 1},
    ))

    out_of_stock_offers = list(db.offers.find(
        {"active": 1, "stock": {"$lte": 0}},
        {"id": 1, "name": 1, "service_id": 1},
    ))

    # --- Alerts ---
    alerts = []
    for off in out_of_stock_offers:
        alerts.append({"type": "stock_empty", "message": f"Stock épuisé: {off['name']}", "severity": "error", "entity_id": off["id"]})
    for off in low_stock_offers:
        alerts.append({"type": "stock_low", "message": f"Stock faible ({off['stock']}): {off['name']}", "severity": "warning", "entity_id": off["id"]})

    old_pending = db.orders.count_documents({
        "status": "pending_payment",
        "created_at": {"$lt": now - 3600},
    })
    if old_pending:
        alerts.append({"type": "old_pending", "message": f"{old_pending} commande(s) en attente depuis plus d'1h", "severity": "warning"})

    unanswered_tickets = db.support_tickets.count_documents({"status": "waiting_admin"})
    if unanswered_tickets:
        alerts.append({"type": "unanswered_tickets", "message": f"{unanswered_tickets} ticket(s) sans réponse", "severity": "warning"})

    paid_not_delivered = db.orders.count_documents({
        "status": {"$in": ["paid", "payment_confirmed", "preparing_delivery"]},
        "paid_at": {"$lt": now - 900},
    })
    if paid_not_delivered:
        alerts.append({
            "type": "paid_not_delivered",
            "message": f"{paid_not_delivered} commande(s) payée(s) non livrée(s) depuis plus de 15 min",
            "severity": "error",
        })

    failed_payments = db.orders.count_documents({
        "status": {"$in": ["verification_failed", "manual_review"]},
    })
    if failed_payments:
        alerts.append({
            "type": "payment_review",
            "message": f"{failed_payments} paiement(s) nécessitent une intervention",
            "severity": "warning",
        })

    recent_errors = db.audit_events.count_documents({
        "action": {"$in": ["system.error", "webhook.error", "delivery.error"]},
        "created_at": {"$gte": datetime.fromtimestamp(now - 86400, UTC)},
    })
    if recent_errors:
        alerts.append({
            "type": "recent_errors",
            "message": f"{recent_errors} erreur(s) système durant les dernières 24 h",
            "severity": "error",
        })

    # --- Services enrichis ---
    services_enriched = []
    for svc in db.services.find({}).sort([("sort_order", ASCENDING), ("id", ASCENDING)]):
        svc_data = _public(svc)
        offers = list(db.offers.find({"service_id": svc["id"]}))
        svc_data["offers"] = [_public(offer) for offer in offers]
        svc_data["offer_count"] = len(offers)
        svc_data["total_stock"] = sum(o.get("stock", 0) for o in offers)
        # Count sales
        svc_data["total_sales"] = db.orders.count_documents({
            "offer_id": {"$in": [o["id"] for o in offers]},
            "status": {"$in": paid_statuses},
        }) if offers else 0
        offer_ids = [offer["id"] for offer in offers]
        svc_data["total_revenue"] = _revenue({
            "offer_id": {"$in": offer_ids},
            "status": {"$in": paid_statuses},
        }) if offer_ids else 0.0
        services_enriched.append(svc_data)

    summary = {
        "users": total_users,
        "new_users_today": new_users_today,
        "new_users_7d": new_users_7d,
        "new_users_prev_7d": new_users_prev_7d,
        "orders": total_orders,
        "orders_today": orders_today,
        "orders_yesterday": orders_yesterday,
        "orders_day_delta": orders_today - orders_yesterday,
        "pending_orders": pending_orders,
        "paid_orders": paid_orders,
        "delivered_orders": delivered_orders,
        "revenue_today": revenue_today,
        "revenue_yesterday": revenue_yesterday,
        "revenue_day_delta": round(revenue_today - revenue_yesterday, 2),
        "revenue_7d": revenue_7d,
        "revenue_30d": revenue_30d,
        "revenue_prev_7d": revenue_prev_7d,
        "revenue_7d_change_pct": round(
            ((revenue_7d - revenue_prev_7d) / revenue_prev_7d * 100) if revenue_prev_7d else (100.0 if revenue_7d else 0.0),
            1,
        ),
        "users_7d_change_pct": round(
            ((new_users_7d - new_users_prev_7d) / new_users_prev_7d * 100)
            if new_users_prev_7d else (100.0 if new_users_7d else 0.0),
            1,
        ),
        "conversion_rate": conversion_rate,
        "open_tickets": open_tickets,
        "low_stock_offers": len(low_stock_offers),
        "available_inventory": available_inventory,
        "failed_payments": failed_payments,
        "paid_not_delivered": paid_not_delivered,
        "recent_errors": recent_errors,
    }

    return {
        "summary": summary,
        "alerts": alerts,
        "orders": list_orders(limit=50),
        "services": services_enriched,
        "users": list_users(limit=200),
        "tickets": list_tickets(limit=50),
        "audits": list_audit_events(limit=100),
        "interactions": interaction_analytics(days=30, limit=1000),
        **shop_settings(),
    }


def create_ticket(user_id, message):
    tid = _next_id("tickets")
    get_conn().support_tickets.insert_one({"id": tid, "user_id": user_id, "message": message[:2000], "status": "open", "created_at": datetime.now(UTC)})
    audit_event("ticket.created", user_id, {"ticket_id": tid})
    return tid


def list_tickets(status="open", limit=50):
    return [_public(x) for x in get_conn().support_tickets.find({"status": status}).sort("created_at", DESCENDING).limit(limit)]


def get_ticket(ticket_id):
    return _public(get_conn().support_tickets.find_one({"id": ticket_id}))


def close_ticket(ticket_id):
    return bool(get_conn().support_tickets.update_one({"id": ticket_id}, {"$set": {"status": "closed", "closed_at": datetime.now(UTC)}}).matched_count)


def list_users(limit=100):
    return [_public(x) for x in get_conn().users.find({}).sort("created_at", DESCENDING).limit(limit)]


def list_broadcast_users():
    """Return every active bot user eligible for private announcements."""
    return [
        _public(row)
        for row in get_conn().users.find(
            {
                "telegram_id": {"$exists": True},
                "banned": {"$ne": True},
                "broadcast_blocked": {"$ne": True},
            },
            {"telegram_id": 1, "lang": 1},
        )
    ]


def mark_broadcast_blocked(user_id, blocked=True):
    get_conn().users.update_one(
        {"telegram_id": int(user_id)},
        {"$set": {"broadcast_blocked": bool(blocked)}},
    )


def set_user_banned(user_id, banned):
    result = get_conn().users.update_one({"telegram_id": user_id}, {"$set": {"banned": bool(banned)}})
    audit_event("user.banned" if banned else "user.unbanned", details={"user_id": user_id})
    return bool(result.matched_count)


def is_user_banned(user_id):
    row = get_conn().users.find_one({"telegram_id": user_id}, {"banned": 1})
    return bool(row and row.get("banned"))


def list_audit_events(limit=100):
    return [_public(x) for x in get_conn().audit_events.find({}).sort("created_at", DESCENDING).limit(limit)]
