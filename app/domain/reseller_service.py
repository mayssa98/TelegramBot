"""Server-side client and catalog mapping for external reseller suppliers."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import database as db
from config import MAILREADER_API_BASE, MAILREADER_API_KEY

PROVIDER = "mailreader"


class ResellerApiError(RuntimeError):
    """A safe, administrator-facing supplier error."""


def _request_json(path: str) -> dict[str, Any]:
    if not MAILREADER_API_KEY:
        raise ResellerApiError(
            "MailReader n’est pas configuré. Ajoutez HP_MAILREADER_API_KEY "
            "dans les variables d’environnement."
        )
    request = Request(
        f"{MAILREADER_API_BASE}{path}",
        headers={
            "Authorization": f"Bearer {MAILREADER_API_KEY}",
            "Accept": "application/json",
            "User-Agent": "BlackMarket-Reseller/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise ResellerApiError(
                "Clé API MailReader refusée. Remplacez-la par une clé active."
            ) from exc
        raise ResellerApiError(f"MailReader a répondu avec l’erreur HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ResellerApiError("MailReader est temporairement indisponible.") from exc
    if not isinstance(payload, dict):
        raise ResellerApiError("Réponse MailReader invalide.")
    return payload


def catalog() -> dict[str, Any]:
    """Fetch the live supplier catalog and overlay local retail selections."""
    payload = _request_json("/api/reseller/products")
    reseller = payload.get("reseller") if isinstance(payload.get("reseller"), dict) else {}
    raw_products = payload.get("products")
    if not isinstance(raw_products, list):
        raise ResellerApiError("Le catalogue MailReader ne contient aucune liste de produits.")

    saved = {
        row["product_id"]: row
        for row in db.list_reseller_product_configs(PROVIDER)
    }
    products = []
    for raw in raw_products:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        product_id = str(raw["id"])
        try:
            wholesale = float(Decimal(str(raw.get("wholesale_price", "0"))))
        except (InvalidOperation, ValueError):
            wholesale = 0.0
        stock = max(0, int(raw.get("stock") or 0))
        config = saved.get(product_id, {})
        retail_price = config.get("retail_price")
        products.append({
            "id": product_id,
            "name": str(raw.get("name") or product_id)[:200],
            "description": str(raw.get("description") or "")[:2000],
            "delivery_instruction": str(raw.get("delivery_instruction") or "")[:2000],
            "wholesale_price": wholesale,
            "currency": str(raw.get("currency") or "USDT")[:12],
            "stock": stock,
            "enabled": bool(config.get("enabled", False)),
            "retail_price": float(retail_price) if retail_price is not None else None,
            "profit": (
                round(float(retail_price) - wholesale, 2)
                if retail_price is not None else None
            ),
        })
    return {
        "ok": True,
        "configured": True,
        "provider": PROVIDER,
        "supplier_name": str(reseller.get("name") or "MailReader"),
        "balance": float(Decimal(str(reseller.get("balance", "0")))),
        "currency": "USDT",
        "products": products,
        "selected_count": sum(1 for product in products if product["enabled"]),
    }


def save_product(
    product_id: str,
    *,
    name: str,
    wholesale_price: float,
    currency: str,
    retail_price: float,
    enabled: bool,
) -> dict[str, Any]:
    """Validate and save one product's resale settings."""
    if not str(product_id).strip():
        raise ValueError("Produit fournisseur invalide.")
    wholesale_price = max(0.0, float(wholesale_price))
    retail_price = float(retail_price)
    if retail_price < 0:
        raise ValueError("Le prix client ne peut pas être négatif.")
    if enabled and retail_price <= wholesale_price:
        raise ValueError("Le prix client doit être supérieur au prix grossiste.")
    return db.save_reseller_product_config(
        PROVIDER,
        str(product_id),
        name=name,
        wholesale_price=wholesale_price,
        currency=currency,
        retail_price=retail_price,
        enabled=enabled,
    )


def save_catalog_product(
    product_id: str, *, retail_price: float, enabled: bool,
) -> dict[str, Any]:
    """Save one live catalog item without trusting supplier fields from the browser."""
    product = next(
        (item for item in catalog()["products"] if item["id"] == str(product_id)),
        None,
    )
    if not product:
        raise ValueError("Ce produit n’est plus disponible chez MailReader.")
    return save_product(
        product["id"],
        name=product["name"],
        wholesale_price=product["wholesale_price"],
        currency=product["currency"],
        retail_price=retail_price,
        enabled=enabled,
    )
