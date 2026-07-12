"""Vercel serverless endpoint for Telegram webhook updates and Admin Dashboard."""

from __future__ import annotations

import asyncio
import base64
import csv
import hmac
import html
import io
import json
import logging
import os
import threading
import traceback
from datetime import UTC, datetime
from enum import Enum
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from telegram import Update
from telegram.constants import ParseMode

import database as db
from api.dashboard import render_dashboard
from app import __version__
from app.domain import inventory_service, order_service, payment_service, support_service
from app.web import dashboard_api
from bot import build_app
from config import CURRENCY, DASHBOARD_PASSWORD

_loop = asyncio.new_event_loop()
_app = None
_runtime_lock = threading.Lock()
log = logging.getLogger(__name__)


def health_payload() -> dict:
    """Return a public, non-sensitive health response."""
    return {
        "ok": True,
        "service": "TelegramBot webhook",
        "version": __version__,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _application():
    global _app
    if _app is None:
        candidate = build_app()
        _loop.run_until_complete(candidate.initialize())
        _app = candidate
    return _app


class handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, payload: dict):
        body = json.dumps(payload, default=self._json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _reply_bytes(self, status: int, body: bytes, content_type: str, filename: str | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _json_default(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        return str(value)

    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path.rstrip("/")

        if path == "/admin":
            if not self._dashboard_authorized():
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="TelegramBot Admin"')
                self.end_headers()
                return

            # Servir le dashboard HTML
            try:
                data = db.dashboard_data()
                data["shop_name"] = os.environ.get("HP_SHOP_NAME", "BlackMarket").strip()
                data["currency"] = CURRENCY
                body = render_dashboard(data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store, max-age=0")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                traceback.print_exc()
                self._reply(500, {"ok": False, "error": str(exc)})
            return

        elif path == "/admin/api/data":
            if not self._dashboard_authorized():
                self._reply(401, {"ok": False, "error": "Unauthorized"})
                return
            try:
                data = db.dashboard_data()
                data["shop_name"] = os.environ.get("HP_SHOP_NAME", "BlackMarket").strip()
                data["currency"] = CURRENCY
                self._reply(200, data)
            except Exception as exc:
                self._reply(500, {"ok": False, "error": str(exc)})
            return

        elif path == "/admin/api/ticket-messages":
            if not self._dashboard_authorized():
                self._reply(401, {"ok": False, "error": "Unauthorized"})
                return
            try:
                query = parse_qs(url.query)
                ticket_id = int(query.get("ticket_id", [0])[0])
                messages = support_service.get_messages(ticket_id)
                self._reply(200, messages)
            except Exception as exc:
                self._reply(500, {"ok": False, "error": str(exc)})
            return

        elif path == "/admin/api/orders":
            if not self._dashboard_authorized():
                self._reply(401, {"ok": False, "error": "Unauthorized"})
                return
            self._reply(200, dashboard_api.list_orders(parse_qs(url.query)))
            return

        elif path == "/admin/api/tickets":
            if not self._dashboard_authorized():
                self._reply(401, {"ok": False, "error": "Unauthorized"})
                return
            self._reply(200, dashboard_api.list_tickets(parse_qs(url.query)))
            return

        elif path == "/admin/api/inventory":
            if not self._dashboard_authorized():
                self._reply(401, {"ok": False, "error": "Unauthorized"})
                return
            params = parse_qs(url.query)
            if params:
                self._reply(200, dashboard_api.list_inventory(params))
            else:
                self._reply(200, {"items": dashboard_api.inventory_summary()})
            return

        elif path == "/admin/api/customers":
            if not self._dashboard_authorized():
                self._reply(401, {"ok": False, "error": "Unauthorized"})
                return
            params = parse_qs(url.query)
            user_id = params.get("user_id", [""])[0]
            if user_id.isdigit():
                customer = dashboard_api.customer_detail(int(user_id))
                self._reply(200 if customer else 404, customer or {"ok": False, "error": "Not found"})
            else:
                self._reply(200, dashboard_api.list_customers(params))
            return

        elif path == "/admin/api/inventory-export":
            if not self._dashboard_authorized():
                self._reply(401, {"ok": False, "error": "Unauthorized"})
                return
            params = parse_qs(url.query)
            result = dashboard_api.list_inventory({**params, "page": ["1"], "per_page": ["100"]})
            items = list(result["items"])
            for page in range(2, result["pages"] + 1):
                page_result = dashboard_api.list_inventory({**params, "page": [str(page)], "per_page": ["100"]})
                items.extend(page_result["items"])
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(("reference_id", "offer_id", "masked_preview", "status", "order_id", "created_at"))
            for item in items:
                writer.writerow((
                    item.get("reference_id"),
                    item.get("offer_id"),
                    item.get("masked_preview"),
                    item.get("status"),
                    item.get("reserved_order_id") or item.get("delivered_order_id") or "",
                    item.get("created_at", ""),
                ))
            self._reply_bytes(
                200,
                output.getvalue().encode("utf-8-sig"),
                "text/csv; charset=utf-8",
                "inventory-masked.csv",
            )
            return

        # Health check par défaut
        self._reply(200, health_payload())

    def _dashboard_authorized(self) -> bool:
        if not DASHBOARD_PASSWORD:
            return False
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            _, password = base64.b64decode(header[6:]).decode().split(":", 1)
            return hmac.compare_digest(password, DASHBOARD_PASSWORD)
        except Exception:
            return False

    def do_POST(self):
        path = urlsplit(self.path).path.rstrip("/")
        if path == "/admin":
            self._dashboard_action()
            return

        # Webhook Telegram
        secret = os.environ.get("HP_WEBHOOK_SECRET", "")
        supplied = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not secret or supplied != secret:
            self._reply(403, {"ok": False, "error": "invalid webhook secret"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            update_id = payload.get("update_id")
            if update_id is None or not db.claim_update(update_id):
                self._reply(200, {"ok": True, "duplicate": True})
                return
            with _runtime_lock:
                app = _application()
                update = Update.de_json(payload, app.bot)
                _loop.run_until_complete(app.process_update(update))
            self._reply(200, {"ok": True})
        except Exception as exc:
            if "update_id" in locals() and update_id is not None:
                db.release_update(update_id)
            traceback.print_exc()
            log.exception(
                "webhook_processing_failed update_id=%s",
                update_id if "update_id" in locals() else None,
            )
            self.log_error("Webhook processing failed: %s", exc)
            self._reply(500, {"ok": False})

    def _dashboard_action(self):
        if not self._dashboard_authorized():
            self._reply(401, {"ok": False, "error": "Unauthorized"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 500000:
                raise ValueError("Request too large")
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(size).decode(), keep_blank_values=True).items()}
            action = form.get("action")

            if action == "add_service":
                name = form["name"].strip()[:80]
                emoji = form.get("emoji", "📦")[:12]
                sid = db.add_service(name, emoji)
                db.audit_event("service.created", details={"service_id": sid, "name": name})

            elif action == "update_service":
                sid = int(form["service_id"])
                name = form["name"].strip()[:80]
                emoji = form.get("emoji", "")[:12]
                db.update_service(sid, name=name, emoji=emoji)
                db.audit_event("service.updated", details={"service_id": sid, "name": name})

            elif action == "toggle_service":
                sid = int(form["service_id"])
                service = db.get_service(sid)
                db.update_service(sid, active=0 if service["active"] else 1)
                db.audit_event("service.toggled", details={"service_id": sid, "active": not service["active"]})

            elif action == "add_offer":
                sid = int(form["service_id"])
                name = form["name"].strip()[:120]
                price = float(form["price"])
                stock = int(form.get("stock", 0))
                note = form.get("note", "")[:250]
                description = form.get("description", "").strip()[:1000]
                auto_delivery = form.get("auto_delivery", "") == "on"
                low_stock_threshold = max(0, int(form.get("low_stock_threshold", 5)))
                delivery_delay = form.get("delivery_delay", "").strip()[:120]
                oid = db.add_offer(
                    sid,
                    name,
                    price,
                    stock,
                    note,
                    description=description,
                    auto_delivery=auto_delivery,
                    low_stock_threshold=low_stock_threshold,
                    delivery_delay=delivery_delay,
                )
                db.audit_event("offer.created", details={"offer_id": oid, "name": name})

            elif action == "update_offer":
                oid = int(form["offer_id"])
                name = form["name"].strip()[:120]
                price = None if form.get("price", "") == "" else float(form["price"])
                stock = max(0, int(form["stock"]))
                note = form.get("note", "")[:250]
                db.update_offer(
                    oid,
                    price=price,
                    stock=stock,
                    name=name,
                    note=note,
                    description=form.get("description", "").strip()[:1000],
                    sort_order=max(0, int(form.get("sort_order", 0))),
                    auto_delivery=form.get("auto_delivery", "") == "on",
                    low_stock_threshold=max(0, int(form.get("low_stock_threshold", 5))),
                    delivery_delay=form.get("delivery_delay", "").strip()[:120],
                )
                db.audit_event("offer.updated", details={"offer_id": oid, "name": name})

            elif action == "toggle_offer":
                oid = int(form["offer_id"])
                offer = db.get_offer(oid)
                db.update_offer(oid, active=0 if offer["active"] else 1)
                db.audit_event("offer.toggled", details={"offer_id": oid, "active": not offer["active"]})

            elif action == "add_inventory":
                oid = int(form["offer_id"])
                items = form.get("items", "").splitlines()
                count = inventory_service.add_items(oid, items)
                db.audit_event("inventory.added", details={"offer_id": oid, "count": count})

            elif action == "toggle_inventory":
                item_id = int(form["inventory_id"])
                disabled = form.get("disabled", "1") == "1"
                if not inventory_service.set_disabled(item_id, disabled):
                    raise ValueError("L'article ne peut pas changer d'état")

            elif action == "reveal_inventory":
                item_id = int(form["inventory_id"])
                value = inventory_service.reveal_item(item_id)
                if value is None:
                    raise ValueError("Article introuvable")
                self._reply(200, {"ok": True, "value": value})
                return

            elif action == "toggle_ban":
                uid = int(form["user_id"])
                banned = bool(int(form["banned"]))
                db.set_user_banned(uid, banned)

            elif action == "close_ticket":
                tid = int(form["ticket_id"])
                support_service.close_ticket(tid)

            elif action == "reply_ticket":
                tid = int(form["ticket_id"])
                message = form.get("message", "").strip()
                if message:
                    support_service.add_message(tid, 0, message, sender_type="admin")
                    # Notifier le client sur Telegram
                    ticket = support_service.get_ticket(tid)
                    if ticket:
                        app = _application()
                        try:
                            _loop.run_until_complete(
                                app.bot.send_message(
                                    ticket["user_id"],
                                    f"🎫 <b>Réponse du Support (Ticket #{tid})</b>\n\n{html.escape(message)}",
                                    parse_mode=ParseMode.HTML,
                                )
                            )
                        except Exception as e:
                            print(f"Failed to notify user about ticket reply: {e}")

            elif action == "confirm_payment":
                oid = int(form["order_id"])
                if payment_service.confirm_payment_manual(oid):
                    # Tenter la livraison automatique
                    delivered = inventory_service.deliver_for_order(oid)
                    order = db.get_order(oid)
                    app = _application()
                    if delivered:
                        content = "\n\n".join(delivered)
                        try:
                            # Notifier le client avec la livraison
                            _loop.run_until_complete(
                                app.bot.send_message(
                                    order["user_id"],
                                    f"🎁 <b>Votre commande #{oid} est livrée !</b>\n\n"
                                    f"Service : <b>{html.escape(order['service_name'])}</b> — {html.escape(order['offer_name'])}\n\n"
                                    f"<code>{html.escape(content)}</code>\n\n"
                                    f"Merci pour votre confiance ! 💜",
                                    parse_mode=ParseMode.HTML,
                                )
                            )
                        except Exception as e:
                            print(f"Failed to deliver notification to user: {e}")
                    else:
                        # Notifier simplement que le paiement est validé
                        try:
                            _loop.run_until_complete(
                                app.bot.send_message(
                                    order["user_id"],
                                    f"✅ <b>Paiement confirmé !</b> Commande #{oid}\n\n"
                                    f"Votre produit sera livré manuellement très bientôt. Merci !",
                                    parse_mode=ParseMode.HTML,
                                )
                            )
                        except Exception as e:
                            print(f"Failed to notify user: {e}")

            elif action == "cancel_order":
                oid = int(form["order_id"])
                reason = form.get("reason", "").strip()
                if order_service.cancel_order(oid, reason):
                    order = db.get_order(oid)
                    app = _application()
                    try:
                        _loop.run_until_complete(
                            app.bot.send_message(
                                order["user_id"],
                                f"❌ <b>Commande #{oid} annulée</b>\n\nRaison : {html.escape(reason or 'Annulée par l admin')}",
                                parse_mode=ParseMode.HTML,
                            )
                        )
                    except Exception as e:
                        print(f"Failed to notify cancellation to user: {e}")

            elif action == "reset_order":
                oid = int(form["order_id"])
                if not order_service.reset_for_payment(oid):
                    raise ValueError("La commande ne peut pas être remise en attente")

            elif action == "refund_order":
                oid = int(form["order_id"])
                reason = form.get("reason", "").strip()[:500]
                if not order_service.mark_refunded(oid, reason):
                    raise ValueError("La commande ne peut pas être remboursée")
                order = db.get_order(oid)
                _loop.run_until_complete(
                    _application().bot.send_message(
                        order["user_id"],
                        f"💸 <b>Commande #{oid} remboursée</b>\n\n{html.escape(reason)}",
                        parse_mode=ParseMode.HTML,
                    )
                )

            elif action == "resend_delivery":
                oid = int(form["order_id"])
                order = db.get_order(oid)
                content = inventory_service.delivered_content(oid)
                if not order or not content:
                    raise ValueError("Aucune livraison automatique à renvoyer")
                _loop.run_until_complete(
                    _application().bot.send_message(
                        order["user_id"],
                        f"🎁 <b>Livraison de la commande #{oid}</b>\n\n<code>{html.escape(chr(10).join(content))}</code>",
                        parse_mode=ParseMode.HTML,
                    )
                )

            elif action == "message_customer":
                oid = int(form["order_id"])
                message = form.get("message", "").strip()[:2000]
                order = db.get_order(oid)
                if not order or not message:
                    raise ValueError("Commande ou message invalide")
                _loop.run_until_complete(
                    _application().bot.send_message(order["user_id"], html.escape(message), parse_mode=ParseMode.HTML)
                )
                db.audit_event("customer.message_sent", details={"order_id": oid, "user_id": order["user_id"]})

            elif action == "save_order_note":
                oid = int(form["order_id"])
                note = form.get("note", "").strip()
                db.get_conn().orders.update_one({"id": oid}, {"$set": {"admin_note": note}})
                db.audit_event("order.note_updated", details={"order_id": oid})

            elif action == "save_settings":
                shop_name = form.get("shop_name", "BlackMarket").strip()
                currency = form.get("currency", "USDT").strip()
                low_stock = int(form.get("low_stock_threshold", 5))
                expiry = int(form.get("order_expiry_seconds", 1800))
                payment_recipient = form.get("payment_recipient", "").strip()
                maintenance_enabled = form.get("maintenance_enabled", "") == "on"
                maintenance_message = form.get("maintenance_message", "").strip()[:500]
                affiliate_enabled = form.get("affiliate_enabled", "") == "on"
                affiliate_target = max(1, int(form.get("affiliate_target", 10)))
                affiliate_reward_cents = max(0, int(form.get("affiliate_reward_cents", 100)))
                active_languages = ",".join(
                    code for code in ("fr", "en", "ar") if code in form.get("active_languages", "fr,en,ar").split(",")
                ) or "fr"

                db.set_setting("shop_name", shop_name)
                db.set_setting("currency", currency)
                db.set_setting("low_stock_threshold", low_stock)
                db.set_setting("order_expiry_seconds", expiry)
                db.set_setting("payment_recipient", payment_recipient)
                db.set_setting("maintenance_enabled", maintenance_enabled)
                db.set_setting("maintenance_message", maintenance_message)
                db.set_setting("affiliate_enabled", affiliate_enabled)
                db.set_setting("affiliate_target", affiliate_target)
                db.set_setting("affiliate_reward_cents", affiliate_reward_cents)
                db.set_setting("welcome_message", form.get("welcome_message", "").strip()[:2000])
                db.set_setting("help_message", form.get("help_message", "").strip()[:4000])
                db.set_setting("terms_message", form.get("terms_message", "").strip()[:4000])
                db.set_setting("privacy_message", form.get("privacy_message", "").strip()[:4000])
                db.set_setting("active_languages", active_languages)
                db.audit_event("settings.updated")

            else:
                raise ValueError(f"Unknown action: {action}")

            self._reply(200, {"ok": True})
        except Exception as exc:
            traceback.print_exc()
            self._reply(400, {"ok": False, "error": str(exc)})
