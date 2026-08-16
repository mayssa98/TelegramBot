"""Tunisia-only storefront catalog and manual-payment orders."""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import re
import secrets
import time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

from pymongo import ReturnDocument

import database as db
from app.constants import InventoryStatus
from app.domain import inventory_service
from config import TN_TND_PER_USDT, TN_WHATSAPP_NUMBER

MAX_PROOF_BYTES = 4_000_000
PAYMENT_METHODS = {
    "d17": {"fr": "D17", "ar": "D17"},
    "flouci": {"fr": "Flouci", "ar": "Flouci"},
    "isi": {"fr": "ISI", "ar": "ISI"},
    "bank_transfer": {"fr": "Virement bancaire", "ar": "تحويل بنكي"},
    "postal_transfer": {"fr": "Virement postal", "ar": "تحويل بريدي"},
}
ALLOWED_PROOF_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "application/pdf": (b"%PDF-",),
}
CATEGORY_LABELS = {
    "ai": {"fr": "Outils IA", "ar": "أدوات الذكاء الاصطناعي"},
    "streaming": {"fr": "Streaming", "ar": "الترفيه والبث"},
    "design": {"fr": "Design & création", "ar": "التصميم والإبداع"},
    "productivity": {"fr": "Productivité", "ar": "الإنتاجية"},
    "cloud": {"fr": "Cloud & Dev", "ar": "السحابة والتطوير"},
    "communication": {"fr": "Communication", "ar": "التواصل"},
    "security": {"fr": "Sécurité", "ar": "الأمان"},
    "other": {"fr": "Autres services", "ar": "خدمات أخرى"},
}
SERVICE_LOGOS = {
    "ai": "https://cdn.simpleicons.org/openai/FFFFFF",
    "chatgpt plus": "https://cdn.simpleicons.org/openai/FFFFFF",
    "netflix": "https://cdn.simpleicons.org/netflix/E50914",
    "google one pro": "https://cdn.simpleicons.org/google/4285F4",
    "adobe pro": "https://cdn.simpleicons.org/adobe/FF0000",
    "capcut": "https://cdn.simpleicons.org/capcut/FFFFFF",
    "canva": "https://cdn.simpleicons.org/canva/00C4CC",
    "linkidin": "https://cdn.simpleicons.org/linkedin/0A66C2",
    "mails": "https://cdn.simpleicons.org/gmail/EA4335",
    "lovable": "https://cdn.simpleicons.org/lovable/FF6B6B",
    "vpns": "https://cdn.simpleicons.org/protonvpn/6D4AFF",
    "youtube": "https://cdn.simpleicons.org/youtube/FF0000",
    "quillbot": "https://cdn.simpleicons.org/quillbot/499557",
    "framer": "https://cdn.simpleicons.org/framer/FFFFFF",
    "supabase": "https://cdn.simpleicons.org/supabase/3FCF8E",
    "telegram premuim": "https://cdn.simpleicons.org/telegram/26A5E4",
}
DEFAULT_SERVICE_LOGO = "/storefront/service-fallback.png"


class StorefrontError(ValueError):
    """Safe validation error for the public storefront."""


def _localized(row: dict[str, Any], field: str, lang: str) -> str:
    suffix = "ar" if lang == "ar" else "fr"
    return str(row.get(f"{field}_{suffix}") or row.get(field) or "").strip()


def _site_visible(row: dict[str, Any]) -> bool:
    channels = row.get("sales_channels")
    if isinstance(channels, list):
        return "tn_site" in channels
    return row.get("site_enabled") is not False


def _price_millimes(offer: dict[str, Any]) -> int:
    configured = offer.get("tn_price_millimes")
    if configured is not None:
        try:
            return max(0, int(configured))
        except (TypeError, ValueError):
            pass
    try:
        fallback = Decimal(str(offer.get("price") or 0)) * Decimal(str(TN_TND_PER_USDT)) * 1000
        return max(0, int(fallback.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    except (InvalidOperation, TypeError, ValueError):
        return 0


def _clean_description(value: Any) -> str:
    text = str(value or "").replace("[[HTML]]", " ")
    text = re.sub(r"<tg-emoji\b[^>]*>.*?</tg-emoji>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?(?:blockquote|p|div|li|ul|ol)\b[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()[:600]


def _site_description(offer: dict[str, Any], lang: str) -> str:
    dedicated = offer.get("site_description_ar" if lang == "ar" else "site_description_fr")
    fallback = _localized(offer, "description", lang)
    return _clean_description(dedicated or fallback)


def _safe_image_url(value: Any) -> str:
    url = str(value or "").strip()[:1000]
    if not url:
        return ""
    parsed = urlsplit(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if url.startswith("/storefront/"):
        return url
    return ""


def _site_category(service: dict[str, Any], offer: dict[str, Any]) -> str:
    configured = str(offer.get("site_category") or "").strip().lower()
    if configured in CATEGORY_LABELS:
        return configured
    name = f"{service.get('name', '')} {offer.get('name', '')}".lower()
    if re.search(r"\b(?:ai|ia)\b", name):
        return "ai"
    rules = (
        ("ai", ("chatgpt", "gemini", "claude", "manus", "higgsfield")),
        ("streaming", ("netflix", "spotify", "youtube", "stream")),
        ("design", ("adobe", "canva", "capcut", "framer", "design")),
        ("cloud", ("supabase", "cloud", "hosting", "google one", "developer")),
        ("communication", ("telegram", "discord", "linkedin")),
        ("security", ("otp", "vpn", "security", "number")),
        ("productivity", ("office", "microsoft", "notion", "quillbot", "grammarly")),
    )
    return next((category for category, words in rules if any(word in name for word in words)), "other")


def _service_logo(service: dict[str, Any]) -> str:
    return SERVICE_LOGOS.get(str(service.get("name") or "").strip().lower(), DEFAULT_SERVICE_LOGO)


def catalog(lang: str = "fr") -> dict[str, Any]:
    """Return the active shared bot catalog projected for the Tunisian site."""
    lang = "ar" if lang == "ar" else "fr"
    services = []
    used_categories: set[str] = set()
    for service in db.list_services():
        if not _site_visible(service):
            continue
        products = []
        for offer in db.list_offers(int(service["id"])):
            if not _site_visible(offer):
                continue
            available = bool(offer.get("unlimited_stock") or int(offer.get("stock") or 0) > 0)
            category = _site_category(service, offer)
            used_categories.add(category)
            products.append({
                "id": int(offer["id"]),
                "service_id": int(service["id"]),
                "name": _localized(offer, "name", lang),
                "description": _site_description(offer, lang),
                "warranty": _localized(offer, "note", lang),
                "delivery_delay": _localized(offer, "delivery_delay", lang),
                "price_millimes": _price_millimes(offer),
                "price": _price_millimes(offer) / 1000,
                "currency": "TND",
                "available": available,
                "stock": -1 if offer.get("unlimited_stock") else max(0, int(offer.get("stock") or 0)),
                "featured": bool(offer.get("site_featured")),
                "image_url": _safe_image_url(offer.get("site_image_url")),
                "logo_url": _service_logo(service),
                "category": category,
                "category_label": CATEGORY_LABELS[category][lang],
                "badge": str(offer.get("site_badge_ar" if lang == "ar" else "site_badge") or "").strip()[:60],
                "emoji": offer.get("emoji") or service.get("emoji") or "✦",
            })
        if products:
            services.append({
                "id": int(service["id"]),
                "name": _localized(service, "name", lang),
                "emoji": service.get("emoji") or "◆",
                "logo_url": _service_logo(service),
                "products": products,
            })
    return {
        "ok": True,
        "lang": lang,
        "currency": "TND",
        "whatsapp": TN_WHATSAPP_NUMBER,
        "services": services,
        "categories": [
            {"id": key, "label": labels[lang]}
            for key, labels in CATEGORY_LABELS.items()
            if key in used_categories
        ],
        "payment_methods": [
            {"id": key, "label": labels[lang]}
            for key, labels in PAYMENT_METHODS.items()
        ],
    }


def _normalize_tunisian_phone(raw: Any) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    if digits.startswith("00216"):
        digits = digits[5:]
    elif digits.startswith("216"):
        digits = digits[3:]
    if not re.fullmatch(r"[2459]\d{7}", digits):
        raise StorefrontError("Utilisez un numéro tunisien valide à 8 chiffres (+216).")
    return f"+216{digits}"


def _decode_proof(payload: dict[str, Any]) -> tuple[bytes, str, str]:
    proof = payload.get("proof")
    if not isinstance(proof, dict):
        raise StorefrontError("Le reçu de paiement est obligatoire.")
    mime_type = str(proof.get("type") or "").lower().strip()
    if mime_type not in ALLOWED_PROOF_TYPES:
        raise StorefrontError("Le reçu doit être une image JPG/PNG ou un PDF.")
    encoded = str(proof.get("data") or "")
    if "," in encoded and encoded.startswith("data:"):
        encoded = encoded.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise StorefrontError("Le fichier du reçu est invalide.") from exc
    if not raw or len(raw) > MAX_PROOF_BYTES:
        raise StorefrontError("Le reçu doit faire moins de 4 Mo.")
    if not any(raw.startswith(signature) for signature in ALLOWED_PROOF_TYPES[mime_type]):
        raise StorefrontError("Le contenu du reçu ne correspond pas à son format.")
    filename = re.sub(r"[^A-Za-z0-9._-]", "_", str(proof.get("name") or "receipt"))[:100]
    return raw, mime_type, filename


def create_order(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a manual-review site order and keep its receipt encrypted."""
    name = re.sub(r"\s+", " ", str(payload.get("name") or "").strip())[:100]
    if len(name) < 2:
        raise StorefrontError("Le nom du client est obligatoire.")
    phone = _normalize_tunisian_phone(payload.get("phone"))
    email = str(payload.get("email") or "").strip().lower()[:200]
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise StorefrontError("Adresse e-mail invalide.")
    try:
        offer_id = int(payload.get("offer_id"))
        quantity = int(payload.get("quantity") or 1)
    except (TypeError, ValueError) as exc:
        raise StorefrontError("Produit ou quantité invalide.") from exc
    if quantity < 1 or quantity > 10:
        raise StorefrontError("La quantité doit être comprise entre 1 et 10.")
    offer = db.get_offer(offer_id)
    service = db.get_service(int(offer.get("service_id"))) if offer else None
    if not offer or not service or not _site_visible(offer) or not _site_visible(service):
        raise StorefrontError("Ce produit n’est plus disponible sur le site tunisien.")
    if not offer.get("unlimited_stock") and int(offer.get("stock") or 0) < quantity:
        raise StorefrontError("Stock insuffisant pour cette commande.")
    payment_method = str(payload.get("payment_method") or "").strip()
    if payment_method not in PAYMENT_METHODS:
        raise StorefrontError("Choisissez une méthode de paiement valide.")
    transaction_reference = str(payload.get("transaction_reference") or "").strip()[:120]
    if len(transaction_reference) < 4:
        raise StorefrontError("La référence du transfert est obligatoire.")
    raw_proof, mime_type, filename = _decode_proof(payload)

    conn = db.get_conn()
    if conn.site_orders.find_one({
        "payment_method": payment_method,
        "transaction_reference": transaction_reference,
        "status": {"$ne": "rejected"},
    }):
        raise StorefrontError("Cette référence de paiement a déjà été utilisée.")
    # Share the global order sequence so inventory reservations never collide
    # with Telegram orders.
    order_id = db._next_id("orders")
    tracking_token = secrets.token_urlsafe(24)
    now = int(time.time())
    unit_price = _price_millimes(offer)
    order = {
        "id": order_id,
        "sales_channel": "tn_site",
        "customer_name": name,
        "phone": phone,
        "email": email,
        "offer_id": offer_id,
        "offer_name": str(offer.get("name") or "")[:200],
        "service_name": str(service.get("name") or "")[:120],
        "quantity": quantity,
        "unit_price_millimes": unit_price,
        "total_millimes": unit_price * quantity,
        "currency": "TND",
        "payment_method": payment_method,
        "transaction_reference": transaction_reference,
        "status": "manual_review",
        "tracking_token_hash": hashlib.sha256(tracking_token.encode()).hexdigest(),
        "created_at": now,
        "updated_at": now,
    }
    conn.site_orders.insert_one(order)
    conn.storefront_payment_proofs.insert_one({
        "order_id": order_id,
        "encrypted_payload": db._fernet().encrypt(raw_proof).decode(),
        "mime_type": mime_type,
        "filename": filename,
        "size": len(raw_proof),
        "created_at": now,
    })
    db.audit_event(
        "storefront.order_submitted",
        details={"order_id": order_id, "offer_id": offer_id, "payment_method": payment_method},
    )
    return {
        "ok": True,
        "order_id": order_id,
        "tracking_token": tracking_token,
        "status": "manual_review",
        "total_millimes": order["total_millimes"],
        "total": order["total_millimes"] / 1000,
        "currency": "TND",
    }


def order_status(order_id: int, tracking_token: str) -> dict[str, Any]:
    """Return a customer-safe order status using a non-stored tracking secret."""
    token_hash = hashlib.sha256(str(tracking_token or "").encode()).hexdigest()
    row = db.get_conn().site_orders.find_one({
        "id": int(order_id),
        "tracking_token_hash": token_hash,
    })
    if not row:
        raise StorefrontError("Commande introuvable.")
    delivery = []
    for encrypted in row.get("encrypted_delivery", []):
        try:
            delivery.append(db._fernet().decrypt(encrypted.encode()).decode())
        except Exception:
            continue
    return {
        "ok": True,
        "order": {
            "id": row["id"],
            "offer_name": row.get("offer_name", ""),
            "service_name": row.get("service_name", ""),
            "quantity": row.get("quantity", 1),
            "total": int(row.get("total_millimes") or 0) / 1000,
            "currency": "TND",
            "payment_method": row.get("payment_method", ""),
            "status": row.get("status", "manual_review"),
            "rejection_reason": row.get("rejection_reason", ""),
            "delivery": delivery,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        },
    }


def list_admin_orders(status: str = "manual_review") -> list[dict[str, Any]]:
    """Return manual site payments for the authenticated dashboard."""
    allowed = {"all", "manual_review", "paid", "payment_confirmed", "delivered", "rejected", "stock_issue"}
    status = status if status in allowed else "manual_review"
    query = {} if status == "all" else {"status": status}
    rows = db.get_conn().site_orders.find(query).sort("created_at", -1).limit(200)
    result = []
    for row in rows:
        item = db._public(row)
        item.pop("tracking_token_hash", None)
        item.pop("encrypted_delivery", None)
        item["total"] = int(item.get("total_millimes") or 0) / 1000
        item["has_proof"] = bool(
            db.get_conn().storefront_payment_proofs.find_one({"order_id": item["id"]}, {"_id": 1})
        )
        result.append(item)
    return result


def payment_proof(order_id: int) -> tuple[bytes, str, str]:
    """Decrypt a receipt only for an explicitly authenticated admin request."""
    row = db.get_conn().storefront_payment_proofs.find_one({"order_id": int(order_id)})
    if not row:
        raise StorefrontError("Reçu introuvable.")
    raw = db._fernet().decrypt(row["encrypted_payload"].encode())
    db.audit_event("storefront.payment_proof_viewed", details={"order_id": int(order_id)})
    return raw, row.get("mime_type", "application/octet-stream"), row.get("filename", "receipt")


def review_order(order_id: int, *, approved: bool, admin_id: int, reason: str = "") -> dict[str, Any]:
    """Accept or reject one manual payment exactly once."""
    conn = db.get_conn()
    order_id = int(order_id)
    now = int(time.time())
    if not approved:
        row = conn.site_orders.find_one_and_update(
            {"id": order_id, "status": "manual_review"},
            {"$set": {
                "status": "rejected",
                "rejection_reason": str(reason or "Paiement non validé").strip()[:500],
                "reviewed_by": int(admin_id),
                "reviewed_at": now,
                "updated_at": now,
            }},
            return_document=ReturnDocument.AFTER,
        )
        if not row:
            raise StorefrontError("Cette commande a déjà été traitée.")
        db.audit_event("storefront.payment_rejected", actor_id=admin_id, details={"order_id": order_id})
        return {"id": order_id, "status": "rejected"}

    row = conn.site_orders.find_one_and_update(
        {"id": order_id, "status": "manual_review"},
        {"$set": {
            "status": "payment_confirmed",
            "reviewed_by": int(admin_id),
            "reviewed_at": now,
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not row:
        raise StorefrontError("Cette commande a déjà été traitée.")
    offer = db.get_offer(int(row["offer_id"])) or {}
    if not offer.get("auto_delivery") or offer.get("unlimited_stock") or offer.get("manual_stock"):
        conn.site_orders.update_one(
            {"id": order_id, "status": "payment_confirmed"},
            {"$set": {"status": "paid", "updated_at": int(time.time())}},
        )
        db.audit_event("storefront.payment_approved", actor_id=admin_id, details={"order_id": order_id})
        return {"id": order_id, "status": "paid"}

    reserved = inventory_service.reserve_for_order(
        int(row["offer_id"]), order_id, int(row.get("quantity") or 1),
    )
    if not reserved:
        conn.site_orders.update_one(
            {"id": order_id, "status": "payment_confirmed"},
            {"$set": {"status": "stock_issue", "updated_at": int(time.time())}},
        )
        db.audit_event("storefront.stock_issue", actor_id=admin_id, details={"order_id": order_id})
        return {"id": order_id, "status": "stock_issue"}

    cipher = db._fernet()
    delivery_values = []
    try:
        for item in reserved:
            raw = cipher.decrypt(item["payload"].encode()).decode()
            delivery_values.append(inventory_service.clean_delivery_value(raw))
    except Exception as exc:
        inventory_service.release_for_order(order_id)
        conn.site_orders.update_one(
            {"id": order_id},
            {"$set": {"status": "stock_issue", "updated_at": int(time.time())}},
        )
        raise StorefrontError("Le stock réservé ne peut pas être livré.") from exc

    item_ids = [item["_id"] for item in reserved]
    delivered = conn.inventory.update_many(
        {"_id": {"$in": item_ids}, "status": InventoryStatus.RESERVED, "reserved_order_id": order_id},
        {"$set": {
            "status": InventoryStatus.DELIVERED,
            "delivered_order_id": order_id,
            "delivered_at": int(time.time()),
        }},
    )
    if delivered.modified_count != len(item_ids):
        raise StorefrontError("La livraison a été interrompue par une modification du stock.")
    conn.site_orders.update_one(
        {"id": order_id, "status": "payment_confirmed"},
        {"$set": {
            "status": "delivered",
            "encrypted_delivery": [cipher.encrypt(value.encode()).decode() for value in delivery_values],
            "delivered_at": int(time.time()),
            "updated_at": int(time.time()),
        }},
    )
    inventory_service.sync_offer_stock(int(row["offer_id"]))
    db.audit_event(
        "storefront.order_delivered",
        actor_id=admin_id,
        details={"order_id": order_id, "items_count": len(delivery_values)},
    )
    return {"id": order_id, "status": "delivered"}
