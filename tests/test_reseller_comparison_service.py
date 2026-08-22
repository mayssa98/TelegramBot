"""AI-assisted comparison of equivalent external supplier products."""

import json
from urllib.error import HTTPError

from app.domain import reseller_comparison_service as comparison


def _reset_cache():
    comparison._comparison_cache.update({"expires_at": 0.0, "payload": None})


def test_ai_groups_common_services_and_selects_cheapest_available(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(
        comparison.reseller_service,
        "provider_summaries",
        lambda: [
            {"id": "one", "name": "Supplier One", "configured": True},
            {"id": "two", "name": "Supplier Two", "configured": True},
            {"id": "off", "name": "Disabled", "configured": False},
        ],
    )

    def fake_catalog(provider):
        price = 3.5 if provider == "one" else 2.25
        return {
            "provider": provider,
            "supplier_name": f"Supplier {provider}",
            "products": [{
                "id": f"{provider}-chatgpt",
                "name": "ChatGPT Plus 1 month",
                "description": "Individual subscription, one month",
                "wholesale_price": price,
                "currency": "USD" if provider == "one" else "USDT",
                "stock": 5,
            }],
        }

    monkeypatch.setattr(comparison.reseller_service, "catalog", fake_catalog)
    monkeypatch.setattr(
        comparison,
        "_ai_group_products",
        lambda items: [{
            "label": "ChatGPT Plus — 1 mois",
            "item_ids": [item["item_id"] for item in items],
            "confidence": 0.97,
            "reason": "Même formule et même durée.",
        }],
    )

    result = comparison.compare_catalogs(force=True)

    assert result["method"] == "external_ai"
    assert result["provider_count"] == 2
    assert result["compared_group_count"] == 1
    group = result["groups"][0]
    assert group["currency"] == "USDT"
    assert group["offers"][0]["provider"] == "two"
    assert group["cheapest_item_id"] == group["offers"][0]["item_id"]
    assert group["savings_vs_next"] == 1.25


def test_out_of_stock_low_price_is_not_selected(monkeypatch):
    items = [
        {
            "item_id": "p1", "provider": "one", "provider_name": "One",
            "product_id": "a", "name": "Adobe 12m", "description": "",
            "delivery_instruction": "", "price": 1.0, "currency": "USDT", "stock": 0,
        },
        {
            "item_id": "p2", "provider": "two", "provider_name": "Two",
            "product_id": "b", "name": "Adobe 12m", "description": "",
            "delivery_instruction": "", "price": 2.0, "currency": "USDT", "stock": 3,
        },
    ]

    groups = comparison._rank_groups([{
        "label": "Adobe 12 mois",
        "item_ids": ["p1", "p2"],
        "confidence": 0.9,
        "reason": "Même produit.",
    }], items)

    assert groups[0]["cheapest_item_id"] == "p2"
    assert groups[0]["offers"][0]["item_id"] == "p2"


def test_missing_ai_key_uses_local_fallback(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(
        comparison.reseller_service,
        "provider_summaries",
        lambda: [
            {"id": "one", "name": "One", "configured": True},
            {"id": "two", "name": "Two", "configured": True},
        ],
    )
    monkeypatch.setattr(
        comparison.reseller_service,
        "catalog",
        lambda provider: {
            "provider": provider,
            "supplier_name": provider,
            "products": [{
                "id": provider,
                "name": "Canva Pro 12 months",
                "description": "Premium account",
                "wholesale_price": 4 if provider == "one" else 3,
                "currency": "USDT",
                "stock": 1,
            }],
        },
    )
    monkeypatch.setattr(
        comparison,
        "_ai_group_products",
        lambda _items: (_ for _ in ()).throw(RuntimeError("HP_AI_API_KEY absente")),
    )

    result = comparison.compare_catalogs(force=True)

    assert result["method"] == "local_fallback"
    assert result["compared_group_count"] == 1
    assert result["groups"][0]["offers"][0]["price"] == 3


def test_comparison_cache_avoids_reloading_suppliers(monkeypatch):
    _reset_cache()
    calls = []
    monkeypatch.setattr(
        comparison.reseller_service,
        "provider_summaries",
        lambda: [{"id": "one", "name": "One", "configured": True}],
    )
    monkeypatch.setattr(
        comparison.reseller_service,
        "catalog",
        lambda provider: calls.append(provider) or {
            "provider": provider, "supplier_name": provider, "products": []
        },
    )

    comparison.compare_catalogs(force=True)
    result = comparison.compare_catalogs()

    assert calls == ["one"]
    assert result["cached"] is True


def test_agentrouter_chat_completions_format(monkeypatch):
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            content = json.dumps({
                "groups": [{
                    "label": "Canva Pro 12 mois",
                    "item_ids": ["p1", "p2"],
                    "confidence": 0.95,
                    "reason": "Même formule et même durée.",
                }]
            })
            return json.dumps({
                "choices": [{"message": {"content": content}}]
            }).encode()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(
        comparison,
        "AI_COMPARISON_API_URL",
        "https://agentrouter.org/v1/chat/completions",
    )
    monkeypatch.setattr(comparison, "AI_COMPARISON_API_KEY", "test-router-token")
    monkeypatch.setattr(comparison, "AI_COMPARISON_MODEL", "kimi-k2.6")
    monkeypatch.setattr(comparison, "AI_COMPARISON_MODELS", ("kimi-k2.6",))
    monkeypatch.setattr(comparison, "urlopen", fake_urlopen)
    items = [
        {
            "item_id": "p1", "provider": "one", "name": "Canva Pro 12m",
            "description": "", "delivery_instruction": "",
        },
        {
            "item_id": "p2", "provider": "two", "name": "Canva Pro one year",
            "description": "", "delivery_instruction": "",
        },
    ]

    groups, used_model = comparison._ai_group_products(items)

    request, timeout = requests[0]
    body = json.loads(request.data)
    assert request.full_url == "https://agentrouter.org/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer test-router-token"
    assert timeout == 45
    assert body["model"] == "kimi-k2.6"
    assert body["messages"][0]["role"] == "system"
    assert groups[0]["item_ids"] == ["p1", "p2"]
    assert used_model == "kimi-k2.6"


def test_agentrouter_tries_next_model_when_first_is_unavailable(monkeypatch):
    attempted_models = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            content = json.dumps({"groups": []})
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    def fake_urlopen(request, timeout):
        assert timeout == 45
        model = json.loads(request.data)["model"]
        attempted_models.append(model)
        if model == "claude-one":
            raise HTTPError(request.full_url, 404, "not found", {}, None)
        return FakeResponse()

    monkeypatch.setattr(comparison, "AI_COMPARISON_API_KEY", "test-router-token")
    monkeypatch.setattr(comparison, "AI_COMPARISON_MODELS", ("claude-one", "claude-two", "gpt"))
    monkeypatch.setattr(comparison, "urlopen", fake_urlopen)
    items = [
        {
            "item_id": "p1", "provider": "one", "name": "Canva",
            "description": "", "delivery_instruction": "",
        },
        {
            "item_id": "p2", "provider": "two", "name": "Canva",
            "description": "", "delivery_instruction": "",
        },
    ]

    _groups, used_model = comparison._ai_group_products(items)

    assert attempted_models == ["claude-one", "claude-two"]
    assert used_model == "claude-two"
