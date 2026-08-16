"""Secure admin-managed external API connectors and manual requests."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import database as db

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
ALLOWED_AUTH_TYPES = {"none", "bearer", "api_key"}
BLOCKED_HEADERS = {"connection", "content-length", "host", "proxy-authorization", "transfer-encoding"}
MAX_RESPONSE_BYTES = 100_000


class ExternalApiError(ValueError):
    """Safe validation or request error suitable for the admin UI."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        raise ExternalApiError("Les redirections externes ne sont pas autorisées.")


def _validate_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip()
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ExternalApiError("Utilisez une URL HTTPS publique sans identifiants intégrés.")
    if parsed.port not in (None, 443):
        raise ExternalApiError("Seul le port HTTPS 443 est autorisé.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ExternalApiError("Le domaine de l’API est introuvable.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ExternalApiError("Les adresses locales, privées ou réservées sont interdites.")
    return endpoint


def _parse_headers(raw: str | dict[str, Any] | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise ExternalApiError("Les en-têtes doivent être un objet JSON valide.") from exc
    if not isinstance(value, dict) or len(value) > 20:
        raise ExternalApiError("Les en-têtes doivent être un objet JSON de 20 entrées maximum.")
    headers: dict[str, str] = {}
    for key, item in value.items():
        name = str(key).strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", name) or name.lower() in BLOCKED_HEADERS:
            raise ExternalApiError(f"En-tête non autorisé : {name}")
        headers[name] = str(item)[:2000]
    return headers


def list_connectors() -> list[dict[str, Any]]:
    rows = db.get_conn().external_api_connectors.find({}).sort("id", -1)
    return [
        {
            "id": row["id"],
            "name": row.get("name", "API externe"),
            "endpoint": row.get("endpoint", ""),
            "method": row.get("method", "GET"),
            "auth_type": row.get("auth_type", "none"),
            "auth_header": row.get("auth_header", "X-API-Key"),
            "headers": row.get("headers", {}),
            "body_template": row.get("body_template", ""),
            "active": bool(row.get("active", True)),
            "has_secret": bool(row.get("encrypted_secret")),
            "updated_at": row.get("updated_at"),
        }
        for row in rows
    ]


def save_connector(payload: dict[str, Any]) -> dict[str, Any]:
    collection = db.get_conn().external_api_connectors
    raw_id = str(payload.get("connector_id") or "").strip()
    connector_id = int(raw_id) if raw_id.isdigit() else db._next_id("external_api_connectors")
    existing = collection.find_one({"id": connector_id}) or {}
    name = str(payload.get("name") or "").strip()[:80]
    if not name:
        raise ExternalApiError("Le nom de l’API est obligatoire.")
    endpoint = _validate_endpoint(str(payload.get("endpoint") or ""))
    method = str(payload.get("method") or "GET").upper()
    if method not in ALLOWED_METHODS:
        raise ExternalApiError("Méthode HTTP non autorisée.")
    auth_type = str(payload.get("auth_type") or "none").lower()
    if auth_type not in ALLOWED_AUTH_TYPES:
        raise ExternalApiError("Type d’authentification non autorisé.")
    auth_header = str(payload.get("auth_header") or "X-API-Key").strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", auth_header):
        raise ExternalApiError("Nom d’en-tête d’authentification invalide.")
    secret = str(payload.get("secret") or "").strip()
    encrypted_secret = existing.get("encrypted_secret", "")
    if secret:
        encrypted_secret = db._fernet().encrypt(secret.encode()).decode()
    if auth_type != "none" and not encrypted_secret:
        raise ExternalApiError("La clé ou le token API est obligatoire.")
    body_template = str(payload.get("body_template") or "").strip()[:20_000]
    if body_template:
        try:
            json.loads(body_template)
        except json.JSONDecodeError as exc:
            raise ExternalApiError("Le corps par défaut doit être un JSON valide.") from exc
    now = int(time.time())
    values = {
        "id": connector_id,
        "name": name,
        "endpoint": endpoint,
        "method": method,
        "auth_type": auth_type,
        "auth_header": auth_header,
        "encrypted_secret": encrypted_secret if auth_type != "none" else "",
        "headers": _parse_headers(payload.get("headers")),
        "body_template": body_template,
        "active": True,
        "updated_at": now,
        "created_at": existing.get("created_at", now),
    }
    collection.update_one({"id": connector_id}, {"$set": values}, upsert=True)
    return next(item for item in list_connectors() if item["id"] == connector_id)


def delete_connector(connector_id: int) -> bool:
    return bool(db.get_conn().external_api_connectors.delete_one({"id": int(connector_id)}).deleted_count)


def execute(connector_id: int, body: str | None = None) -> dict[str, Any]:
    row = db.get_conn().external_api_connectors.find_one({"id": int(connector_id), "active": True})
    if not row:
        raise ExternalApiError("Connexion API introuvable.")
    endpoint = _validate_endpoint(row["endpoint"])
    headers = {**row.get("headers", {})}
    encrypted = row.get("encrypted_secret", "")
    if encrypted:
        secret = db._fernet().decrypt(encrypted.encode()).decode()
        if row.get("auth_type") == "bearer":
            headers["Authorization"] = f"Bearer {secret}"
        elif row.get("auth_type") == "api_key":
            headers[row.get("auth_header") or "X-API-Key"] = secret
    raw_body = (body if body is not None else row.get("body_template", "")).strip()
    request_body = None
    if raw_body and row["method"] != "GET":
        try:
            request_body = json.dumps(json.loads(raw_body)).encode()
        except json.JSONDecodeError as exc:
            raise ExternalApiError("Le corps de la requête doit être un JSON valide.") from exc
        headers.setdefault("Content-Type", "application/json")
    request = Request(endpoint, data=request_body, headers=headers, method=row["method"])
    started = time.monotonic()
    try:
        with build_opener(_NoRedirect()).open(request, timeout=12) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ExternalApiError("La réponse dépasse la limite de 100 Ko.")
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except HTTPError as exc:
        raw = exc.read(min(MAX_RESPONSE_BYTES, 20_000))
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
    except (TimeoutError, URLError) as exc:
        raise ExternalApiError("Connexion impossible ou délai dépassé.") from exc
    text = raw.decode("utf-8", errors="replace")
    try:
        preview: Any = json.loads(text)
    except json.JSONDecodeError:
        preview = text[:20_000]
    return {
        "ok": 200 <= status < 300,
        "status": status,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "content_type": content_type,
        "response": preview,
    }
