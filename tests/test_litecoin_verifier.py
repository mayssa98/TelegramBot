"""Litecoin blockchain validation and LTC/USDT quote tests."""

import litecoin_verifier


def test_litecoin_verifier_sums_only_outputs_to_configured_address(monkeypatch):
    address = "0x6529804d712d5ef4bef5c60af4a3683bd7300411"
    monkeypatch.setattr(litecoin_verifier, "LTC_MIN_CONFIRMATIONS", 3)
    monkeypatch.setattr(litecoin_verifier, "LTC_MIN_DEPOSIT", 0.001)
    def rpc(method, _params):
        if method == "eth_getTransactionReceipt":
            return {"status": "0x1", "blockNumber": "0x10", "logs": [
                {"address": litecoin_verifier.LTC_BSC_TOKEN_CONTRACT,
                 "topics": [litecoin_verifier.TRANSFER_TOPIC, "0x0", "0x" + "0" * 24 + address[2:]],
                 "data": "0x1d4c0"},
                {"address": litecoin_verifier.LTC_BSC_TOKEN_CONTRACT,
                 "topics": [litecoin_verifier.TRANSFER_TOPIC, "0x0", "0x" + "0" * 24 + address[2:]],
                 "data": "0x13880"},
            ]}
        if method == "eth_blockNumber":
            return "0x14"
        raise AssertionError(method)
    monkeypatch.setattr(litecoin_verifier, "_rpc", rpc)

    result = litecoin_verifier.verify_litecoin_deposit(
        "0x" + "a" * 64, address, created_at=1_757_505_000,
    )

    assert result["status"] == "confirmed"
    assert result["ltc_amount"] == 0.002
    assert result["confirmations"] == 5


def test_litecoin_verifier_waits_for_confirmations(monkeypatch):
    monkeypatch.setattr(litecoin_verifier, "LTC_MIN_CONFIRMATIONS", 3)
    monkeypatch.setattr(
        litecoin_verifier,
        "_rpc",
        lambda method, _params: {"eth_getTransactionReceipt": {"status": "0x1", "blockNumber": "0x10", "logs": []}, "eth_blockNumber": "0x11"}[method],
    )

    result = litecoin_verifier.verify_litecoin_deposit(
        "0x" + "a" * 64, "0x6529804d712d5ef4bef5c60af4a3683bd7300411",
    )

    assert result["status"] == "pending"
    assert result["code"] == "confirming"


def test_litecoin_verifier_rejects_wrong_recipient(monkeypatch):
    monkeypatch.setattr(litecoin_verifier, "LTC_MIN_CONFIRMATIONS", 3)
    monkeypatch.setattr(
        litecoin_verifier,
        "_rpc",
        lambda method, _params: {"eth_getTransactionReceipt": {"status": "0x1", "blockNumber": "0x10", "logs": []}, "eth_blockNumber": "0x20"}[method],
    )

    result = litecoin_verifier.verify_litecoin_deposit(
        "0x" + "a" * 64, "0x6529804d712d5ef4bef5c60af4a3683bd7300411",
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
