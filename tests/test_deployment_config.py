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


def test_admin_catalog_declares_delete_confirmation_state():
    source = (PROJECT_ROOT / "admin-ui" / "src" / "AdminPages.jsx").read_text(
        encoding="utf-8"
    )

    assert "const [deleteTarget, setDeleteTarget] = useState(null);" in source


def test_react_admin_sends_scoped_token_for_write_requests():
    app_source = (PROJECT_ROOT / "admin-ui" / "src" / "App.jsx").read_text(
        encoding="utf-8"
    )
    pages_source = (
        PROJECT_ROOT / "admin-ui" / "src" / "AdminPages.jsx"
    ).read_text(encoding="utf-8")

    expected_header = '"X-Dashboard-Write-Token"'
    assert expected_header in app_source
    assert expected_header in pages_source
