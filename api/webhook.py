"""Vercel serverless endpoint for Telegram webhook updates."""
import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler

from telegram import Update

from bot import build_app

_loop = asyncio.new_event_loop()
_app = None


def _application():
    global _app
    if _app is None:
        _app = build_app()
        _loop.run_until_complete(_app.initialize())
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
        self._reply(200, {"ok": True, "service": "TelegramBot webhook"})

    def do_POST(self):
        secret = os.environ.get("HP_WEBHOOK_SECRET", "")
        supplied = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not secret or supplied != secret:
            self._reply(403, {"ok": False, "error": "invalid webhook secret"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            app = _application()
            update = Update.de_json(payload, app.bot)
            _loop.run_until_complete(app.process_update(update))
            self._reply(200, {"ok": True})
        except Exception as exc:
            self.log_error("Webhook processing failed: %s", exc)
            self._reply(500, {"ok": False})
