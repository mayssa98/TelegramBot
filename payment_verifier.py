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


def _transaction_memo(transaction):
    for key in ("note", "memo", "remark", "comments", "reference"):
        value = transaction.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def verify_payment(txid, amount, currency=None, created_at=None, expected_memo=None):
    txid = (txid or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", txid):
        return {"status": "failed", "code": "invalid_format", "reason": "Format de transaction invalide"}
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        return {"status": "failed", "code": "not_configured", "reason": "Vérification automatique non configurée"}

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
            if expected_memo is not None and _transaction_memo(transaction) != str(expected_memo):
                return {"status": "failed", "code": "wrong_memo", "reason": "Notes / Memo incorrect ou absent"}
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
        return {"status": "failed", "code": "not_configured", "reason": "Vérification automatique non configurée"}
    start_ms = ((created_at or int(time.time()) - 86400) * 1000) - 600_000
    try:
        minimum = Decimal(str(minimum_amount))
        for transaction in _fetch_pay_transactions(start_ms):
            if str(transaction.get("transactionId", "")).strip() != txid:
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


def _transaction_time_ms(transaction):
    for key in ("transactionTime", "createTime", "time", "insertTime", "timestamp"):
        value = transaction.get(key)
        if value is None:
            continue
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        return value if value > 10_000_000_000 else value * 1000
    return None


def verify_payment_by_amount(amount, currency=None, created_at=None, used_txids=None, expected_memo=None):
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        return {"status": "failed", "code": "not_configured", "reason": "Vérification automatique non configurée"}

    created_at = int(created_at or time.time())
    start_ms = (created_at * 1000) - 30_000
    used_txids = {str(item).strip() for item in (used_txids or []) if item}
    try:
        expected = Decimal(str(amount)).quantize(Decimal("0.00000001"))
        expected_asset = str(currency or PAY_CURRENCY).upper()
        transactions = _fetch_pay_transactions(start_ms)
        for transaction in transactions:
            txid = str(transaction.get("transactionId", "")).strip()
            if not txid or txid in used_txids:
                continue
            transaction_ms = _transaction_time_ms(transaction)
            if transaction_ms is not None and transaction_ms < start_ms:
                continue
            received = Decimal(str(transaction.get("amount", "0"))).quantize(
                Decimal("0.00000001")
            )
            asset = str(transaction.get("currency", "")).upper()
            if received <= 0 or asset != expected_asset:
                continue
            if received == expected:
                if expected_memo is not None and _transaction_memo(transaction) != str(expected_memo):
                    continue
                return {
                    "status": "confirmed",
                    "code": "confirmed",
                    "txid": txid,
                    "reason": "Paiement Binance Pay confirmé par montant exact",
                }
        return {"status": "failed", "code": "not_found", "reason": "Aucun paiement exact récent détecté"}
    except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, InvalidOperation) as exc:
        return {"status": "failed", "code": "temporary_error", "reason": f"API Binance indisponible: {exc}"}
