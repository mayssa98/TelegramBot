"""MongoDB persistence for users, catalogue, orders, and affiliate data."""
import time

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import MONGODB_DB, MONGODB_URI

_client = None
_db = None


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
    db = get_conn()
    db.command("ping")
    db.users.create_index("telegram_id", unique=True)
    db.services.create_index([("sort_order", ASCENDING), ("id", ASCENDING)])
    db.services.create_index("id", unique=True)
    db.offers.create_index("id", unique=True)
    db.offers.create_index([("service_id", ASCENDING), ("id", ASCENDING)])
    db.orders.create_index("id", unique=True)
    db.orders.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.orders.create_index("status")
    db.orders.create_index("txid", unique=True, partialFilterExpression={"txid": {"$gt": ""}})
    db.settings.create_index("key", unique=True)
    db.referrals.create_index("referred_id", unique=True)
    db.referrals.create_index("referrer_id")
    db.wallets.create_index("user_id", unique=True)
    db.affiliate_rewards.create_index([("referrer_id", ASCENDING), ("milestone", ASCENDING)], unique=True)
    db.pending_states.create_index("user_id", unique=True)
    _seed_catalog()


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


def get_service(service_id):
    return _public(get_conn().services.find_one({"id": service_id}))


def list_offers(service_id, active_only=True):
    query = {"service_id": service_id}
    if active_only:
        query["active"] = 1
    return [_public(x) for x in get_conn().offers.find(query).sort("id", ASCENDING)]


def get_offer(offer_id):
    return _public(get_conn().offers.find_one({"id": offer_id}))


def service_total_stock(service_id):
    result = list(get_conn().offers.aggregate([{"$match": {"service_id": service_id, "active": 1}}, {"$group": {"_id": None, "total": {"$sum": "$stock"}}}]))
    return result[0]["total"] if result else 0


def update_offer(offer_id, price=None, stock=None, name=None, note=None, active=None):
    values = {k: v for k, v in {"price": price, "stock": stock, "name": name, "note": note, "active": active}.items() if v is not None}
    if values:
        get_conn().offers.update_one({"id": offer_id}, {"$set": values})


def add_service(name, emoji=""):
    db = get_conn()
    last = db.services.find_one(sort=[("sort_order", DESCENDING)])
    sid = _next_id("services")
    db.services.insert_one({"id": sid, "name": name, "emoji": emoji, "sort_order": (last or {}).get("sort_order", 0) + 1, "active": 1})
    return sid


def update_service(service_id, name=None, emoji=None, active=None):
    values = {k: v for k, v in {"name": name, "emoji": emoji, "active": active}.items() if v is not None}
    return bool(values and get_conn().services.update_one({"id": service_id}, {"$set": values}).matched_count)


def archive_service(service_id):
    db = get_conn()
    db.services.update_one({"id": service_id}, {"$set": {"active": 0}})
    db.offers.update_many({"service_id": service_id}, {"$set": {"active": 0}})


def archive_offer(offer_id):
    return update_offer(offer_id, active=0)


def add_offer(service_id, name, price, stock, note=""):
    oid = _next_id("offers")
    get_conn().offers.insert_one({"id": oid, "service_id": service_id, "name": name, "price": price, "stock": stock, "note": note, "active": 1})
    return oid


def decrement_stock(offer_id, qty):
    get_conn().offers.update_one({"id": offer_id}, [{"$set": {"stock": {"$max": [0, {"$subtract": ["$stock", qty]}]}}}])


def mark_order_paid(order_id, verify_method):
    db = get_conn()
    order = db.orders.find_one({"id": order_id})
    if not order or order.get("status") in ("paid", "delivered"):
        return bool(order)
    if order.get("status") not in ("awaiting_verification", "pending_payment"):
        return False
    if order.get("offer_id"):
        stock = db.offers.update_one({"id": order["offer_id"], "stock": {"$gte": order["qty"]}}, {"$inc": {"stock": -order["qty"]}})
        if stock.modified_count != 1:
            return False
    paid = db.orders.update_one({"id": order_id, "status": order["status"]}, {"$set": {"status": "paid", "verify_method": verify_method, "updated_at": int(time.time())}})
    if paid.modified_count != 1 and order.get("offer_id"):
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


def list_orders(status=None, limit=30):
    query = {"status": status} if status else {}
    return [_public(x) for x in get_conn().orders.find(query).sort("id", DESCENDING).limit(limit)]


def list_user_orders(user_id, limit=15):
    return [_public(x) for x in get_conn().orders.find({"user_id": user_id}).sort("id", DESCENDING).limit(limit)]


def get_setting(key, default=None):
    row = get_conn().settings.find_one({"key": key})
    return row.get("value", default) if row else default


def set_setting(key, value):
    get_conn().settings.update_one({"key": key}, {"$set": {"value": str(value)}}, upsert=True)


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
