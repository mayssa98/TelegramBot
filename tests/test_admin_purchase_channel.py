"""Regression tests ensuring purchases remain private."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from admin import notify_manual_delivery_request, notify_new_order, post_purchase_to_channel


def _order():
    return {
        "id": 901,
        "user_id": 42,
        "service_name": "Canva",
        "offer_name": "Canva Pro",
        "qty": 1,
        "total_price": 3.0,
        "status": "payment_confirmed",
        "txid": "test-transaction",
    }


def test_direct_purchase_channel_announcement_is_disabled():
    bot = SimpleNamespace(get_me=AsyncMock(), send_message=AsyncMock())

    sent = asyncio.run(post_purchase_to_channel(SimpleNamespace(bot=bot), _order()))

    assert sent is False
    bot.get_me.assert_not_awaited()
    bot.send_message.assert_not_awaited()


def test_new_order_notifies_only_the_private_admin():
    bot = SimpleNamespace(send_message=AsyncMock())

    asyncio.run(notify_new_order(SimpleNamespace(bot=bot), _order()))

    bot.send_message.assert_awaited_once()


def test_manual_delivery_request_notifies_only_the_private_admin():
    bot = SimpleNamespace(send_message=AsyncMock())

    asyncio.run(notify_manual_delivery_request(SimpleNamespace(bot=bot), _order()))

    bot.send_message.assert_awaited_once()


def test_order_detail_text_renders_table_format_when_delivered():
    from admin import order_detail_text
    order = {
        "id": 901,
        "user_id": 42,
        "service_name": "Canva",
        "offer_name": "Canva Pro",
        "qty": 1,
        "total_price": 3.0,
        "status": "delivered",
        "txid": "test-transaction",
        "warranty_days": 30,
    }
    text = order_detail_text(order)
    assert "┌" in text and "┬" in text and "┐" in text
    assert "│ Commande" in text
    assert "│ Statut" in text
    assert "│ Livraison" in text
    assert "LIVRÉE" in text
    assert "OUI (Délivrée)" in text
    assert "DÉLIVRÉE" in text


def test_order_detail_text_renders_table_format_when_not_delivered():
    from admin import order_detail_text
    order = {
        "id": 902,
        "user_id": 42,
        "service_name": "Netflix",
        "offer_name": "Premium",
        "qty": 1,
        "total_price": 5.0,
        "status": "payment_confirmed",
        "txid": "test-transaction",
        "warranty_days": 0,
    }
    text = order_detail_text(order)
    assert "┌" in text and "┬" in text and "┐" in text
    assert "│ Commande" in text
    assert "│ Statut" in text
    assert "│ Livraison" in text
    assert "NON (Manuelle)" in text
    assert "NON DÉLIVRÉE" in text

