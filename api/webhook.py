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
        if self.path.rstrip("/") == "/admin":
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
        page = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>TelegramBot Admin</title><style>body{{font-family:system-ui;background:#08111f;color:#e8eef8;margin:0;padding:32px}}main{{max-width:1100px;margin:auto}}h1{{color:#67e8f9}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}}article,table{{background:#111d2e;border:1px solid #26364d;border-radius:12px}}article{{padding:18px;display:grid;gap:12px}}strong{{font-size:28px}}table{{width:100%;margin-top:24px;border-collapse:collapse;overflow:hidden}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #26364d}}.status{{color:#67e8f9}}small{{color:#94a3b8}}</style></head>
<body><main><h1>HEAVENPREM Admin</h1><small>Live MongoDB overview</small><section class='cards'>{cards}</section><table><thead><tr><th>Order</th><th>Service</th><th>Offer</th><th>Total</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></main></body></html>"""
        body = page.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
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
