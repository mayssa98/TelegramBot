"""Litecoin blockchain validation and LTC/USDT quote tests."""

import litecoin_verifier


def test_litecoin_verifier_sums_only_outputs_to_configured_address(monkeypatch):
    address = "LgSoW9DoZkgd4TwY3SGs4FsM6eynNbzzv7"
    monkeypatch.setattr(litecoin_verifier, "LTC_MIN_CONFIRMATIONS", 3)
    monkeypatch.setattr(litecoin_verifier, "LTC_MIN_DEPOSIT", 0.001)
    monkeypatch.setattr(
        litecoin_verifier,
        "_request_json",
        lambda _url: {
            "confirmations": 4,
            "received": "2026-09-10T12:00:00Z",
            "outputs": [
                {"value": 120_000, "addresses": [address]},
                {"value": 50_000, "addresses": ["LotherAddress"]},
                {"value": 80_000, "addresses": [address]},
            ],
        },
    )

    result = litecoin_verifier.verify_litecoin_deposit(
        "a" * 64, address, created_at=1_757_505_000,
    )

    assert result["status"] == "confirmed"
    assert result["ltc_amount"] == 0.002
    assert result["confirmations"] == 4


def test_litecoin_verifier_waits_for_confirmations(monkeypatch):
    monkeypatch.setattr(litecoin_verifier, "LTC_MIN_CONFIRMATIONS", 3)
    monkeypatch.setattr(
        litecoin_verifier,
        "_request_json",
        lambda _url: {"confirmations": 1, "outputs": []},
    )

    result = litecoin_verifier.verify_litecoin_deposit(
        "a" * 64, "LgSoW9DoZkgd4TwY3SGs4FsM6eynNbzzv7",
    )

    assert result["status"] == "pending"
    assert result["code"] == "confirming"


def test_litecoin_verifier_rejects_wrong_recipient(monkeypatch):
    monkeypatch.setattr(litecoin_verifier, "LTC_MIN_CONFIRMATIONS", 3)
    monkeypatch.setattr(
        litecoin_verifier,
        "_request_json",
        lambda _url: {
            "confirmations": 6,
            "outputs": [{"value": 100_000_000, "addresses": ["LotherAddress"]}],
        },
    )

    result = litecoin_verifier.verify_litecoin_deposit(
        "a" * 64, "LgSoW9DoZkgd4TwY3SGs4FsM6eynNbzzv7",
    )

    assert result["status"] == "failed"
    assert result["code"] == "wrong_recipient"


def test_fetch_ltc_usdt_quote_uses_public_price(monkeypatch):
    monkeypatch.setattr(
        litecoin_verifier, "_request_json", lambda _url: {"price": "82.12500000"},
    )

    result = litecoin_verifier.fetch_ltc_usdt_quote()

    assert result["status"] == "confirmed"
    assert result["price"] == 82.125
    assert result["source"] == "binance_ltcusdt"
