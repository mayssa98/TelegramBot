"""Railway safeguards for services with region-sensitive upstream APIs."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_railway_runs_single_webhook_replica_in_europe():
    config = json.loads((PROJECT_ROOT / "railway.json").read_text(encoding="utf-8"))

    deploy = config["deploy"]
    assert deploy["startCommand"] == "python railway_server.py"
    assert deploy["healthcheckPath"] == "/health"
    assert deploy["multiRegionConfig"] == {
        "europe-west4-drams3a": {"numReplicas": 1}
    }
