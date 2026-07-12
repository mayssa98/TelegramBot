"""Tests for persistent shop settings."""

from __future__ import annotations

import database as db


def test_shop_settings_defaults_and_typed_overrides(mock_mongodb):
    defaults = db.shop_settings()
    assert defaults["maintenance_enabled"] is False
    assert isinstance(defaults["order_expiry_seconds"], int)

    db.set_setting("maintenance_enabled", True)
    db.set_setting("affiliate_target", 25)
    db.set_setting("maintenance_message", "Maintenance planifiée")

    settings = db.shop_settings()
    assert settings["maintenance_enabled"] is True
    assert settings["affiliate_target"] == 25
    assert settings["maintenance_message"] == "Maintenance planifiée"
