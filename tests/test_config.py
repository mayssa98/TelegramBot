"""Tests for deployment environment parsing."""

import config


def test_mongodb_uri_uses_hp_environment_variable(monkeypatch):
    uri = "mongodb+srv://user:password@example.mongodb.net/app"
    monkeypatch.setenv("HP_MONGODB_URI", uri)

    assert config.mongodb_uri_from_environment() == uri


def test_mongodb_uri_unwraps_quotes_from_raw_variable_import(monkeypatch):
    monkeypatch.setenv("HP_MONGODB_URI", "'mongodb://mongo:27017/app'")

    assert config.mongodb_uri_from_environment() == "mongodb://mongo:27017/app"


def test_mongodb_uri_rejects_vercel_sensitive_placeholder(monkeypatch):
    monkeypatch.setenv("HP_MONGODB_URI", "[SENSITIVE]")

    assert config.mongodb_uri_from_environment() == ""


def test_configuration_reports_invalid_mongodb_uri(monkeypatch):
    monkeypatch.setattr(config, "BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ADMIN_ID", 123)
    monkeypatch.setattr(config, "MONGODB_URI", "not-a-mongodb-uri")

    assert config.configuration_issues() == [
        "HP_MONGODB_URI (invalid MongoDB URI)",
    ]
