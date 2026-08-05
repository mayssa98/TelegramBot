"""Vérification en lecture seule dans l'historique Binance Pay."""
import hashlib
import hmac
import json
import re
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import BINANCE_API_BASES, BINANCE_API_KEY, BINANCE_API_SECRET, PAY_CURRENCY


def _signed_pay_request(base_url, start_time):
    params = {
        "startTime": max(0, int(start_time)),
        "endTime": int(time.time() * 1000),
        "limit": 100,
        "recvWindow": 5000,
        "timestamp": int(time.time() * 1000),
    }
    query = urlencode(params)
    signature = hmac.new(
        BINANCE_API_SECRET.encode("utf-8"), query.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    request = Request(
        f"{base_url}/sapi/v1/pay/transactions?{query}&signature={signature}",
        headers={"X-MBX-APIKEY": BINANCE_API_KEY, "Accept": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("success") or payload.get("code") != "000000":
        raise RuntimeError(payload.get("message") or "Réponse Binance invalide")
    return payload.get("data") or []


def _fetch_pay_transactions_with_base(start_time):
    """Try official Binance hosts when a region blocks one host with HTTP 451."""
    failures = []
    for base_url in BINANCE_API_BASES:
        try:
            return _signed_pay_request(base_url, start_time), base_url
        except HTTPError as exc:
            failures.append(f"{base_url}: HTTP {exc.code}")
            if exc.code != 451:
                raise
        except (URLError, TimeoutError) as exc:
            failures.append(f"{base_url}: {type(exc).__name__}")
    raise RuntimeError("Tous les endpoints Binance ont échoué (" + "; ".join(failures) + ")")


def _fetch_pay_transactions(start_time):
    rows, _base_url = _fetch_pay_transactions_with_base(start_time)
    return rows


def binance_healthcheck():
    """Return a secret-free connectivity diagnostic for the admin dashboard."""
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        return {
            "ok": False,
            "code": "not_configured",
            "message": "Clés Binance non configurées",
        }
    start_ms = int((time.time() - 86400) * 1000)
    try:
        rows, base_url = _fetch_pay_transactions_with_base(start_ms)
        return {
            "ok": True,
            "code": "connected",
            "endpoint": base_url,
            "transactions_24h": len(rows),
            "message": "Connexion Binance opérationnelle",
        }
    except Exception as exc:
        return {
            "ok": False,
            "code": "unreachable",
            "message": str(exc)[:1000],
        }


def _transaction_identifiers(transaction):
    """Return every Binance identifier a customer may see on a receipt.

    Binance's Pay history response has an internal ``transactionId`` as well
    as an ``orderId``.  The mobile app labels the latter "Order ID", so either
    value must be accepted when a customer submits the receipt identifier.
    """
    return {
        str(transaction.get(key, "")).strip()
        for key in ("transactionId", "orderId")
        if transaction.get(key) is not None
    } - {""}


def verify_payment(txid, amount, currency=None, created_at=None):
    txid = (txid or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", txid):
        return {"status": "failed", "code": "invalid_format", "reason": "Format de transaction invalide"}
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        return {"status": "failed", "code": "not_configured", "reason": "Vérification TXID non configurée"}

    # Inclure une marge de 10 minutes avant la création de la commande.
    start_ms = ((created_at or int(time.time()) - 3600) * 1000) - 600_000
    try:
        expected = Decimal(str(amount)).quantize(Decimal("0.00000001"))
        transactions = _fetch_pay_transactions(start_ms)
        for transaction in transactions:
            if txid not in _transaction_identifiers(transaction):
                continue
            received = Decimal(str(transaction.get("amount", "0"))).quantize(
                Decimal("0.00000001")
            )
            asset = str(transaction.get("currency", "")).upper()
            if received <= 0:
                return {"status": "failed", "code": "not_incoming", "reason": "La transaction n'est pas un paiement entrant"}
            if asset != PAY_CURRENCY:
                return {"status": "failed", "code": "wrong_currency", "reason": f"Devise reçue: {asset}, attendue: {PAY_CURRENCY}"}
            if received != expected:
                return {"status": "failed", "code": "wrong_amount", "reason": f"Montant reçu: {received}, attendu: {expected}"}
            return {"status": "confirmed", "code": "confirmed", "reason": "Transaction Binance Pay confirmée"}
        return {"status": "failed", "code": "not_found", "reason": "Transaction absente de l'historique Binance Pay"}
    except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, InvalidOperation) as exc:
        return {"status": "failed", "code": "temporary_error", "reason": f"API Binance indisponible: {exc}"}


def verify_incoming_transfer(txid, minimum_amount=1, created_at=None):
    """Verify an incoming TXID and return its real amount for wallet top-ups."""
    txid = (txid or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", txid):
        return {"status": "failed", "code": "invalid_format", "reason": "Format de transaction invalide"}
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        return {"status": "failed", "code": "not_configured", "reason": "Vérification TXID non configurée"}
    start_ms = ((created_at or int(time.time()) - 86400) * 1000) - 600_000
    try:
        minimum = Decimal(str(minimum_amount))
        for transaction in _fetch_pay_transactions(start_ms):
            if txid not in _transaction_identifiers(transaction):
                continue
            amount = Decimal(str(transaction.get("amount", "0")))
            asset = str(transaction.get("currency", "")).upper()
            if asset != PAY_CURRENCY:
                return {"status": "failed", "code": "wrong_currency", "reason": f"Devise reçue: {asset}"}
            if amount < minimum:
                return {"status": "failed", "code": "below_minimum", "reason": f"Montant minimum: {minimum} {PAY_CURRENCY}"}
            return {
                "status": "confirmed",
                "code": "confirmed",
                "amount": float(amount),
                "currency": asset,
                "reason": "Transfert entrant confirmé",
            }
        return {"status": "failed", "code": "not_found", "reason": "Transaction absente de l'historique Binance Pay"}
    except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, InvalidOperation) as exc:
        return {"status": "failed", "code": "temporary_error", "reason": f"API Binance indisponible: {exc}"}
