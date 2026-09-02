"""Tests for read-only BSC and Polygon USDT receipt verification."""

import onchain_verifier as verifier

DESTINATION = "0x6529804d712d5ef4bef5c60af4a3683bd7300411"
SENDER_TOPIC = "0x" + "0" * 24 + "1" * 40


def _recipient_topic(address=DESTINATION):
    return "0x" + "0" * 24 + address.lower().removeprefix("0x")


def _rpc_for_transfer(network, amount_units, *, recipient=DESTINATION, status="0x1"):
    settings = verifier.NETWORKS[network]

    def rpc(_network, method, params):
        assert _network == network
        if method == "eth_chainId":
            return hex(settings["chain_id"])
        if method == "eth_getTransactionReceipt":
            return {
                "status": status,
                "blockNumber": "0x64",
                "logs": [{
                    "address": settings["contract"],
                    "topics": [
                        verifier.TRANSFER_TOPIC,
                        SENDER_TOPIC,
                        _recipient_topic(recipient),
                    ],
                    "data": hex(amount_units),
                }],
            }
        if method == "eth_blockNumber":
            return "0x68"
        if method == "eth_getBlockByNumber":
            assert params[0] == "0x64"
            return {"timestamp": "0x7d0"}
        raise AssertionError(method)

    return rpc


def test_bsc_usdt_transfer_is_confirmed(monkeypatch):
    monkeypatch.setattr(
        verifier, "_rpc", _rpc_for_transfer("bsc", 5 * 10**18),
    )

    result = verifier.verify_onchain_usdt_once(
        "0x" + "a" * 64, "bsc", 5, DESTINATION, created_at=1900,
    )

    assert result["status"] == "confirmed"
    assert result["amount"] == 5.0
    assert result["confirmations"] == 5


def test_polygon_uses_six_decimal_usdt_amount(monkeypatch):
    monkeypatch.setattr(
        verifier, "_rpc", _rpc_for_transfer("polygon", 8250000),
    )

    result = verifier.verify_onchain_usdt_once(
        "0x" + "b" * 64, "polygon", 8.25, DESTINATION,
    )

    assert result["status"] == "confirmed"
    assert result["amount"] == 8.25


def test_wrong_recipient_is_rejected(monkeypatch):
    other = "0x" + "2" * 40
    monkeypatch.setattr(
        verifier, "_rpc", _rpc_for_transfer("bsc", 5 * 10**18, recipient=other),
    )

    result = verifier.verify_onchain_usdt_once(
        "0x" + "c" * 64, "bsc", 5, DESTINATION,
    )

    assert result["status"] == "failed"
    assert result["code"] == "wrong_recipient"


def test_wrong_amount_is_rejected(monkeypatch):
    monkeypatch.setattr(
        verifier, "_rpc", _rpc_for_transfer("polygon", 7000000),
    )

    result = verifier.verify_onchain_usdt_once(
        "0x" + "d" * 64, "polygon", 8, DESTINATION,
    )

    assert result["status"] == "failed"
    assert result["code"] == "wrong_amount"


def test_unmined_transaction_is_pending(monkeypatch):
    def rpc(_network, method, _params):
        return "0x38" if method == "eth_chainId" else None

    monkeypatch.setattr(verifier, "_rpc", rpc)

    result = verifier.verify_onchain_usdt_once(
        "0x" + "e" * 64, "bsc", 5, DESTINATION,
    )

    assert result["status"] == "pending"
    assert result["code"] == "not_mined"


def test_failed_receipt_is_rejected(monkeypatch):
    monkeypatch.setattr(
        verifier, "_rpc", _rpc_for_transfer("bsc", 5 * 10**18, status="0x0"),
    )

    result = verifier.verify_onchain_usdt_once(
        "0x" + "f" * 64, "bsc", 5, DESTINATION,
    )

    assert result["status"] == "failed"
    assert result["code"] == "transaction_failed"


def test_transfer_from_before_payment_request_is_rejected(monkeypatch):
    monkeypatch.setattr(
        verifier, "_rpc", _rpc_for_transfer("polygon", 5000000),
    )

    result = verifier.verify_onchain_usdt_once(
        "0x" + "1" * 64, "polygon", 5, DESTINATION, created_at=3000,
    )

    assert result["status"] == "failed"
    assert result["code"] == "transaction_too_old"
