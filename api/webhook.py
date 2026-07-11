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
        users = db.list_users()
        tickets = db.list_tickets()
        audits = db.list_audit_events()
        user_rows = "".join(f"<tr><td>{u['telegram_id']}</td><td>{html.escape(str(u.get('username') or '—'))}</td><td>{html.escape(str(u.get('first_name') or '—'))}</td><td>{html.escape(str(u.get('lang','fr')))}</td><td><form method='post' action='/admin'><input type='hidden' name='action' value='toggle_ban'><input type='hidden' name='user_id' value='{u['telegram_id']}'><input type='hidden' name='banned' value='{0 if u.get('banned') else 1}'><button class='secondary'>{'Unban' if u.get('banned') else 'Ban'}</button></form></td></tr>" for u in users)
        ticket_rows = "".join(f"<tr><td>#{x['id']}</td><td>{x['user_id']}</td><td>{html.escape(str(x['message']))}</td><td>{x['status']}</td><td><form method='post' action='/admin'><input type='hidden' name='action' value='close_ticket'><input type='hidden' name='ticket_id' value='{x['id']}'><button>Close</button></form></td></tr>" for x in tickets)
        audit_rows = "".join(f"<tr><td>{html.escape(str(x.get('created_at',''))[:19])}</td><td>{html.escape(str(x.get('action','')))}</td><td><code>{html.escape(str(x.get('details',{})))}</code></td></tr>" for x in audits)
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
<title>HEAVENPREM Control Center</title><style>*{{box-sizing:border-box}}body{{font-family:Inter,system-ui;background:#07101d;color:#e8eef8;margin:0}}nav{{position:sticky;top:0;z-index:3;background:#0b1728;border-bottom:1px solid #26364d;padding:14px;display:flex;gap:8px;overflow:auto}}nav button{{white-space:nowrap}}main{{max-width:1280px;margin:auto;padding:28px}}h1,h2{{color:#67e8f9}}.panel{{display:none}}.panel.active{{display:block}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px}}article,table,.service{{background:#111d2e;border:1px solid #26364d;border-radius:12px}}article,.service{{padding:18px}}strong{{font-size:28px}}.tablewrap{{overflow:auto}}table{{width:100%;margin:20px 0;border-collapse:collapse;overflow:hidden}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #26364d;vertical-align:top}}.status{{color:#67e8f9}}small{{color:#94a3b8}}.catalog{{display:grid;gap:18px}}form{{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}}input,textarea,button{{background:#0b1524;color:#e8eef8;border:1px solid #334155;border-radius:8px;padding:10px}}textarea{{width:100%;min-height:90px}}button{{background:#0891b2;border:0;cursor:pointer}}button.secondary,nav button{{background:#334155}}nav button.active{{background:#0891b2}}.offer{{border-top:1px solid #26364d;padding:12px 0}}details{{margin:10px 0}}summary{{cursor:pointer;color:#67e8f9}}#search{{margin-left:auto;min-width:220px}}code{{font-size:11px}}@media(max-width:700px){{main{{padding:15px}}th,td{{padding:8px}}#search{{display:none}}}}</style></head>
<body><nav><button data-tab='overview' class='active'>Overview</button><button data-tab='catalogue'>Catalogue</button><button data-tab='orders'>Orders</button><button data-tab='customers'>Customers</button><button data-tab='support'>Support</button><button data-tab='audit'>Audit</button><input id='search' placeholder='Search current page'></nav><main><h1>HEAVENPREM Control Center</h1><small>Live secure operations • refreshes every 10 seconds</small>
<section id='overview' class='panel active'><h2>Business overview</h2><div class='cards'>{cards}</div></section>
<section id='catalogue' class='panel'><h2>Catalogue & encrypted inventory</h2><form method='post' action='/admin'><input type='hidden' name='action' value='add_service'><input name='name' placeholder='New service name' required><input name='emoji' placeholder='Emoji'><button>Add service</button></form><div class='catalog'>{''.join(service_sections)}</div></section>
<section id='orders' class='panel'><h2>Recent orders</h2><div class='tablewrap'><table><thead><tr><th>Order</th><th>Service</th><th>Offer</th><th>Total</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section id='customers' class='panel'><h2>Customers</h2><div class='tablewrap'><table><thead><tr><th>Telegram ID</th><th>Username</th><th>Name</th><th>Language</th><th>Control</th></tr></thead><tbody>{user_rows}</tbody></table></div></section>
<section id='support' class='panel'><h2>Open support tickets</h2><div class='tablewrap'><table><thead><tr><th>Ticket</th><th>User</th><th>Message</th><th>Status</th><th>Action</th></tr></thead><tbody>{ticket_rows}</tbody></table></div></section>
<section id='audit' class='panel'><h2>Audit history</h2><div class='tablewrap'><table><thead><tr><th>Time</th><th>Action</th><th>Details</th></tr></thead><tbody>{audit_rows}</tbody></table></div></section></main>
<script>const tabs=[...document.querySelectorAll('nav button[data-tab]')],panels=[...document.querySelectorAll('.panel')];tabs.forEach(b=>b.onclick=()=>{{tabs.forEach(x=>x.classList.remove('active'));panels.forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.tab).classList.add('active');location.hash=b.dataset.tab}});if(location.hash)document.querySelector(`[data-tab="${{location.hash.slice(1)}}"]`)?.click();search.oninput=()=>{{const q=search.value.toLowerCase();document.querySelectorAll('.panel.active tr,.panel.active .service').forEach(x=>x.style.display=x.innerText.toLowerCase().includes(q)?'':'none')}};setInterval(()=>{{if(!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName))location.reload()}},10000)</script></body></html>"""
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
            elif action == "toggle_ban":
                uid = int(form["user_id"]); db.set_user_banned(uid, bool(int(form["banned"])))
            elif action == "close_ticket":
                tid = int(form["ticket_id"]); db.close_ticket(tid); db.audit_event("ticket.closed", details={"ticket_id": tid})
            else:
                raise ValueError("Unknown action")
            self.send_response(303); self.send_header("Location", "/admin"); self.end_headers()
        except Exception as exc:
            traceback.print_exc(); self._reply(400, {"ok": False, "error": str(exc)})
