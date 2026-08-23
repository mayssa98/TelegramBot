"""Manual Lovable licensing and extension-file helpers."""
from __future__ import annotations

import hashlib
import time

import database as db

FEATURE_KEY = "lovable_unlimited"
TRIAL_SECONDS = 60 * 60


class LovableError(ValueError):
    pass


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").strip().encode()).hexdigest()


def is_lovable_order(order: dict | None) -> bool:
    if not order or not order.get("offer_id"):
        return False
    offer = db.get_offer(int(order["offer_id"]))
    return bool(offer and offer.get("feature_key") == FEATURE_KEY)


def request_trial(user_id: int) -> tuple[dict, bool]:
    """Create one lifetime trial request for a Telegram customer."""
    conn = db.get_conn()
    existing = conn.lovable_trial_requests.find_one({"user_id": int(user_id)})
    if existing:
        return db._public(existing), False
    now = int(time.time())
    row = {
        "id": db._next_id("lovable_trial_requests"),
        "user_id": int(user_id),
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    conn.lovable_trial_requests.insert_one(row)
    db.audit_event("lovable.trial_requested", actor_id=int(user_id))
    return db._public(row), True


def _register_license(
    *, user_id: int, token: str, duration_seconds: int, plan: str,
    order_id: int | None = None,
) -> dict:
    token = str(token or "").strip()
    if not token:
        raise LovableError("La licence est obligatoire.")
    now = int(time.time())
    selector = {"order_id": int(order_id)} if order_id is not None else {
        "user_id": int(user_id), "plan": str(plan),
    }
    values = {
        "user_id": int(user_id),
        "plan": str(plan),
        "token_hash": _token_hash(token),
        "token_encrypted": db._fernet().encrypt(token.encode()).decode(),
        "created_at": now,
        "expires_at": now + max(1, int(duration_seconds)),
        "revoked": False,
    }
    if order_id is not None:
        values["order_id"] = int(order_id)
    db.get_conn().lovable_licenses.update_one(
        selector,
        {"$set": values, "$setOnInsert": {"id": db._next_id("lovable_licenses")}},
        upsert=True,
    )
    row = db.get_conn().lovable_licenses.find_one(selector)
    db.audit_event(
        "lovable.manual_license_registered",
        actor_id=int(user_id),
        details={"order_id": order_id, "plan": plan},
    )
    return db._public(row)


def register_paid_license(order_id: int, token: str) -> dict:
    """Register the exact license manually supplied by the administrator."""
    order = db.get_order(int(order_id))
    if not order or order.get("status") not in {"paid", "payment_confirmed"}:
        raise LovableError("La commande n’est pas en attente de livraison.")
    offer = db.get_offer(int(order.get("offer_id") or 0))
    if not offer or offer.get("feature_key") != FEATURE_KEY:
        raise LovableError("Cette commande ne concerne pas Lovable Unlimited Credit.")
    days = int(offer.get("duration_days") or 0)
    if days not in {1, 7, 30}:
        raise LovableError("Durée de licence invalide.")
    return _register_license(
        user_id=int(order["user_id"]),
        token=token,
        duration_seconds=days * 24 * 60 * 60,
        plan=f"{days}_day" if days == 1 else f"{days}_days",
        order_id=int(order_id),
    )


def complete_trial(user_id: int, token: str) -> dict:
    request = db.get_conn().lovable_trial_requests.find_one({
        "user_id": int(user_id), "status": "pending",
    })
    if not request:
        raise LovableError("Cette demande d’essai n’est plus en attente.")
    license_row = _register_license(
        user_id=int(user_id), token=token,
        duration_seconds=TRIAL_SECONDS, plan="trial",
    )
    now = int(time.time())
    db.get_conn().lovable_trial_requests.update_one(
        {"_id": request["_id"], "status": "pending"},
        {"$set": {"status": "delivered", "delivered_at": now, "updated_at": now}},
    )
    return license_row


def validate_license(token: str) -> dict:
    normalized = str(token or "").strip()
    row = db.get_conn().lovable_licenses.find_one({"token_hash": _token_hash(normalized)})
    now = int(time.time())
    valid = bool(
        normalized and row and not row.get("revoked")
        and int(row.get("expires_at") or 0) > now
    )
    return {
        "ok": True,
        "valid": valid,
        "plan": str((row or {}).get("plan") or "") if valid else "",
        "expires_at": int((row or {}).get("expires_at") or 0) if valid else 0,
        "server_time": now,
    }


def extension_file() -> dict | None:
    file_id = str(db.get_setting("lovable_extension_file_id", "") or "").strip()
    if not file_id:
        return None
    return {
        "file_id": file_id,
        "file_name": str(
            db.get_setting("lovable_extension_file_name", "lovable-extension.zip")
            or "lovable-extension.zip"
        ),
    }


def set_extension_file(file_id: str, file_name: str) -> dict:
    safe_name = str(file_name or "lovable-extension.zip").strip()[:180]
    if not safe_name.lower().endswith(".zip"):
        raise LovableError("The extension file must be a ZIP archive.")
    db.set_setting("lovable_extension_file_id", str(file_id).strip())
    db.set_setting("lovable_extension_file_name", safe_name)
    return extension_file()
