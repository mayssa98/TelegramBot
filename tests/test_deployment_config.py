"""Deployment safeguards for services with region-sensitive upstream APIs."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_webhook_does_not_run_in_binance_blocked_us_region():
    config = json.loads((PROJECT_ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert config["regions"] == ["dxb1"]
    assert config["functions"]["api/webhook.py"]["regions"] == ["dxb1"]
