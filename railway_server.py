"""Run the complete BlackMarket Telegram service on Railway."""

from __future__ import annotations

import logging
import os
import re
import signal
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config
from api import webhook

log = logging.getLogger("railway")
_TELEGRAM_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


class RailwayHTTPServer(ThreadingHTTPServer):
    """Concurrent HTTP server whose request threads cannot block shutdown."""

    allow_reuse_address = True
    daemon_threads = True


def deployment_issues() -> list[str]:
    """Return safe configuration errors for the all-in-one Railway service."""
    issues = config.configuration_issues(webhook=True)
    webhook_secret = config.env_value("HP_WEBHOOK_SECRET")
    cron_secret = config.env_value("CRON_SECRET")
    if webhook_secret and (
        len(webhook_secret) < 24
        or not _TELEGRAM_SECRET_RE.fullmatch(webhook_secret)
    ):
        issues.append(
            "HP_WEBHOOK_SECRET (at least 24 characters using A-Z, a-z, 0-9, _ or -)"
        )
    if cron_secret and len(cron_secret) < 24:
        issues.append("CRON_SECRET (must contain at least 24 characters)")
    if (
        config.env_value("RAILWAY_ENVIRONMENT_ID")
        and not config.env_value("HP_PUBLIC_BASE_URL")
        and not config.env_value("RAILWAY_PUBLIC_DOMAIN")
    ):
        issues.append("Railway public domain (generate one under Networking)")
    return list(dict.fromkeys(issues))


def register_telegram_webhook(*, attempts: int = 3, retry_seconds: float = 2) -> dict:
    """Register the Railway URL with Telegram, retrying transient failures."""
    result: dict = {"ok": False, "message": "Telegram webhook was not registered."}
    for attempt in range(1, attempts + 1):
        result = webhook.repair_telegram_webhook()
        if result.get("ok"):
            log.info("Telegram webhook registered at %s", result.get("url"))
            return result
        log.warning(
            "Telegram webhook registration attempt %s/%s failed: %s",
            attempt,
            attempts,
            result.get("message", "unknown error"),
        )
        if attempt < attempts:
            time.sleep(retry_seconds)
    return result


def _call_scheduled_endpoint(port: int, path: str, secret: str) -> None:
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        headers={"Authorization": f"Bearer {secret}"},
    )
    try:
        with urlopen(request, timeout=240) as response:
            log.info("Scheduled job %s completed with HTTP %s", path, response.status)
    except HTTPError as exc:
        log.error("Scheduled job %s returned HTTP %s", path, exc.code)
    except (URLError, TimeoutError) as exc:
        log.error("Scheduled job %s could not run: %s", path, exc)


def scheduler_loop(stop_event: threading.Event, port: int) -> None:
    """Replace Vercel cron schedules inside the singleton Railway process."""
    secret = config.env_value("CRON_SECRET")
    intervals = {
        "/api/cron/restock": max(
            60, int(os.environ.get("HP_RESTOCK_INTERVAL_SECONDS", "300"))
        ),
        "/api/cron/prices": max(
            60, int(os.environ.get("HP_PRICE_INTERVAL_SECONDS", "600"))
        ),
    }
    due_at = {path: time.monotonic() + seconds for path, seconds in intervals.items()}
    while not stop_event.is_set():
        next_due = min(due_at.values())
        if stop_event.wait(max(0.0, next_due - time.monotonic())):
            break
        now = time.monotonic()
        for path, due in tuple(due_at.items()):
            if due <= now:
                _call_scheduled_endpoint(port, path, secret)
                due_at[path] = time.monotonic() + intervals[path]


def main() -> None:
    issues = deployment_issues()
    if issues:
        raise RuntimeError("Incomplete Railway configuration: " + ", ".join(issues))

    try:
        port = int(os.environ.get("PORT", "8080"))
    except ValueError as exc:
        raise RuntimeError("PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT must be between 1 and 65535")

    server = RailwayHTTPServer(("0.0.0.0", port), webhook.handler)
    try:
        # Initialize MongoDB and Telegram before Railway marks the deployment healthy.
        webhook._application()
        result = register_telegram_webhook()
        if not result.get("ok"):
            raise RuntimeError(
                result.get("message") or "Telegram webhook registration failed"
            )
    except Exception:
        server.server_close()
        raise

    stop_event = threading.Event()
    scheduler = threading.Thread(
        target=scheduler_loop,
        args=(stop_event, port),
        name="railway-scheduler",
        daemon=True,
    )
    scheduler.start()

    def request_shutdown(_signum, _frame) -> None:
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    log.info(
        "Railway HTTP service listening on 0.0.0.0:%s (public URL: %s)",
        port,
        config.public_base_url_from_environment(),
    )
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop_event.set()
        scheduler.join(timeout=5)
        server.server_close()


if __name__ == "__main__":
    main()
