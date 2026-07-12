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

from config import BINANCE_API_BASE, BINANCE_API_KEY, BINANCE_API_SECRET, PAY_CURRENCY


def _fetch_pay_transactions(start_time):
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
        f"{BINANCE_API_BASE}/sapi/v1/pay/transactions?{query}&signature={signature}",
        headers={"X-MBX-APIKEY": BINANCE_API_KEY, "Accept": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("success") or payload.get("code") != "000000":
        raise RuntimeError(payload.get("message") or "Réponse Binance invalide")
    return payload.get("data") or []


def verify_payment(txid, amount, currency=None, created_at=None):
    txid = (txid or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", txid):
        return {"status": "failed", "code": "invalid_format", "reason": "Format de transaction invalide"}
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        return {"status": "manual_review", "code": "not_configured", "reason": "Vérification automatique non configurée"}

    # Inclure une marge de 10 minutes avant la création de la commande.
    start_ms = ((created_at or int(time.time()) - 3600) * 1000) - 600_000
    try:
        expected = Decimal(str(amount)).quantize(Decimal("0.00000001"))
        transactions = _fetch_pay_transactions(start_ms)
        for transaction in transactions:
            if str(transaction.get("transactionId", "")).strip() != txid:
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
        return {"status": "manual_review", "code": "temporary_error", "reason": f"API Binance indisponible: {exc}"}
