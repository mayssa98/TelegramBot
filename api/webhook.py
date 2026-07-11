"""Vercel serverless endpoint for Telegram webhook updates."""
import asyncio
import base64
import hmac
import html
import json
import os
import threading
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from telegram import Update

from bot import build_app
import database as db
from config import DASHBOARD_PASSWORD

_loop = asyncio.new_event_loop()
_app = None
_runtime_lock = threading.Lock()


def _application():
    global _app
    if _app is None:
        candidate = build_app()
        _loop.run_until_complete(candidate.initialize())
        _app = candidate
    return _app


class handler(BaseHTTPRequestHandler):
    def _reply(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlsplit(self.path).path.rstrip("/") == "/admin":
            if not self._dashboard_authorized():
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="TelegramBot Admin"')
                self.end_headers()
                return
            self._dashboard()
            return
        self._reply(200, {"ok": True, "service": "TelegramBot webhook"})

    def _dashboard_authorized(self):
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

    def _dashboard(self):
        summary = db.dashboard_summary()
        orders = db.list_orders(limit=30)
        rows = "".join(
            f"<tr><td>#{o['id']}</td><td>{html.escape(str(o['service_name']))}</td>"
            f"<td>{html.escape(str(o['offer_name']))}</td><td>${o['total_price']:.2f}</td>"
            f"<td><span class='status'>{html.escape(str(o['status']))}</span></td></tr>"
            for o in orders
        )
        cards = "".join(f"<article><b>{html.escape(k.replace('_',' ').title())}</b><strong>{v}</strong></article>" for k, v in summary.items())
        service_sections = []
        for service in db.list_services(active_only=False):
            offers = db.list_offers(service["id"], active_only=False)
            offer_rows = []
            for offer in offers:
                stats = db.inventory_stats(offer["id"])
                offer_rows.append(f"""<div class='offer'><form method='post' action='/admin'>
<input type='hidden' name='action' value='update_offer'><input type='hidden' name='offer_id' value='{offer['id']}'>
<input name='name' value='{html.escape(str(offer['name']), quote=True)}' required>
<input name='price' type='number' min='0' step='0.01' value='{'' if offer['price'] is None else offer['price']}' placeholder='Price'>
<input name='stock' type='number' min='0' value='{offer['stock']}' placeholder='Stock'>
<input name='note' value='{html.escape(str(offer.get('note','')), quote=True)}' placeholder='Note'>
<button>Save</button></form><form method='post' action='/admin'><input type='hidden' name='action' value='toggle_offer'><input type='hidden' name='offer_id' value='{offer['id']}'><button class='secondary'>{'Disable' if offer['active'] else 'Enable'}</button></form>
<details><summary>🔐 Inventory ({stats['available']} available)</summary><form method='post' action='/admin'><input type='hidden' name='action' value='add_inventory'><input type='hidden' name='offer_id' value='{offer['id']}'><textarea name='items' placeholder='One code or account per line' required></textarea><button>Encrypt & add</button></form></details></div>""")
            service_sections.append(f"""<section class='service'><h3>{html.escape(str(service['emoji']))} {html.escape(str(service['name']))}</h3>
<form method='post' action='/admin'><input type='hidden' name='action' value='update_service'><input type='hidden' name='service_id' value='{service['id']}'><input name='name' value='{html.escape(str(service['name']), quote=True)}' required><input name='emoji' value='{html.escape(str(service['emoji']), quote=True)}'><button>Save service</button></form>
<form method='post' action='/admin'><input type='hidden' name='action' value='toggle_service'><input type='hidden' name='service_id' value='{service['id']}'><button class='secondary'>{'Disable' if service['active'] else 'Enable'} service</button></form>{''.join(offer_rows)}
<details><summary>➕ Add offer</summary><form method='post' action='/admin'><input type='hidden' name='action' value='add_offer'><input type='hidden' name='service_id' value='{service['id']}'><input name='name' placeholder='Offer name' required><input name='price' type='number' min='0' step='0.01' placeholder='Price' required><input name='stock' type='number' min='0' value='0'><input name='note' placeholder='Note'><button>Add offer</button></form></details></section>""")
        page = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>TelegramBot Admin</title><style>body{{font-family:system-ui;background:#08111f;color:#e8eef8;margin:0;padding:32px}}main{{max-width:1200px;margin:auto}}h1,h2{{color:#67e8f9}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}}article,table,.service{{background:#111d2e;border:1px solid #26364d;border-radius:12px}}article,.service{{padding:18px}}strong{{font-size:28px}}table{{width:100%;margin:24px 0;border-collapse:collapse;overflow:hidden}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #26364d}}.status{{color:#67e8f9}}small{{color:#94a3b8}}.catalog{{display:grid;gap:18px}}form{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}}input,textarea,button{{background:#0b1524;color:#e8eef8;border:1px solid #334155;border-radius:8px;padding:9px}}textarea{{width:100%;min-height:90px}}button{{background:#0891b2;border:0;cursor:pointer}}button.secondary{{background:#334155}}.offer{{border-top:1px solid #26364d;padding:12px 0}}details{{margin:10px 0}}summary{{cursor:pointer;color:#67e8f9}}</style></head>
<body><main><h1>HEAVENPREM Admin</h1><small>Secure catalogue and operations dashboard • live refresh every 10 seconds</small><section class='cards'>{cards}</section><h2>Recent orders</h2><table><thead><tr><th>Order</th><th>Service</th><th>Offer</th><th>Total</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table><h2>Catalogue management</h2><form method='post' action='/admin'><input type='hidden' name='action' value='add_service'><input name='name' placeholder='New service name' required><input name='emoji' placeholder='Emoji'><button>Add service</button></form><div class='catalog'>{''.join(service_sections)}</div></main><script>setInterval(()=>{{if(!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName))location.reload()}},10000)</script></body></html>"""
        body = page.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Cache-Control", "no-store, max-age=0"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        if urlsplit(self.path).path.rstrip("/") == "/admin":
            self._dashboard_action()
            return
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
            self.log_error("Webhook processing failed: %s", exc)
            self._reply(500, {"ok": False})

    def _dashboard_action(self):
        if not self._dashboard_authorized():
            self._reply(401, {"ok": False})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 250000:
                raise ValueError("Request too large")
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(size).decode(), keep_blank_values=True).items()}
            action = form.get("action")
            if action == "add_service":
                sid = db.add_service(form["name"].strip()[:80], form.get("emoji", "📦")[:12]); db.audit_event("service.created", details={"service_id": sid})
            elif action == "update_service":
                sid = int(form["service_id"]); db.update_service(sid, name=form["name"].strip()[:80], emoji=form.get("emoji", "")[:12]); db.audit_event("service.updated", details={"service_id": sid})
            elif action == "toggle_service":
                sid = int(form["service_id"]); service = db.get_service(sid); db.update_service(sid, active=0 if service["active"] else 1); db.audit_event("service.toggled", details={"service_id": sid})
            elif action == "add_offer":
                oid = db.add_offer(int(form["service_id"]), form["name"].strip()[:120], float(form["price"]), int(form.get("stock", 0)), form.get("note", "")[:250]); db.audit_event("offer.created", details={"offer_id": oid})
            elif action == "update_offer":
                oid = int(form["offer_id"]); price = None if form.get("price", "") == "" else float(form["price"]); db.update_offer(oid, price=price, stock=max(0, int(form["stock"])), name=form["name"].strip()[:120], note=form.get("note", "")[:250]); db.audit_event("offer.updated", details={"offer_id": oid})
            elif action == "toggle_offer":
                oid = int(form["offer_id"]); offer = db.get_offer(oid); db.update_offer(oid, active=0 if offer["active"] else 1); db.audit_event("offer.toggled", details={"offer_id": oid})
            elif action == "add_inventory":
                oid = int(form["offer_id"]); count = db.add_inventory_items(oid, form.get("items", "").splitlines()); db.audit_event("inventory.added", details={"offer_id": oid, "count": count})
            else:
                raise ValueError("Unknown action")
            self.send_response(303); self.send_header("Location", "/admin"); self.end_headers()
        except Exception as exc:
            traceback.print_exc(); self._reply(400, {"ok": False, "error": str(exc)})
