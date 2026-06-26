import json

import pytest

from q4_llm_extraction import extract_reviews as q4


def make_group(text: str, key: str = "k1") -> q4.DedupGroup:
    normalized = q4.normalize_text(text)
    record = q4.ReviewRecord(
        review_id=f"review-{key}",
        order_id=f"order-{key}",
        review_score=1,
        raw_text=text,
        normalized_text=normalized,
        normalized_text_hash=key,
    )
    return q4.DedupGroup(
        dedup_key=key,
        representative_raw_text=text,
        representative_normalized_text=normalized,
        records=(record,),
    )


def routed(text: str, route: str, key: str) -> q4.RoutedGroup:
    return q4.RoutedGroup(group=make_group(text, key), route=route, reason="test")  # type: ignore[arg-type]


def test_normalize_text_collapses_portuguese_accents_and_punctuation() -> None:
    variants = [
        "Produto não chegou",
        "produto nao chegou.",
        "PRODUTO NÃO CHEGOU!!!",
    ]

    assert {q4.normalize_text(text) for text in variants} == {"produto nao chegou"}


def test_normalize_text_keeps_existing_noise_cleanup() -> None:
    text = "  Olá&nbsp;<b>Cliente</b>!!! https://example.com/x\u200b  "

    assert q4.normalize_text(text) == "ola cliente"


def test_deduplicate_reviews_uses_normalized_text_hash() -> None:
    raw_texts = [
        "Não recebi o produto.",
        "nao recebi o produto!!!",
        "Produto veio quebrado",
    ]
    records = [
        q4.ReviewRecord(
            review_id=f"review-{index}",
            order_id=f"order-{index}",
            review_score=1,
            raw_text=text,
            normalized_text=q4.normalize_text(text),
            normalized_text_hash=q4.hash_normalized_text(q4.normalize_text(text)),
        )
        for index, text in enumerate(raw_texts)
    ]

    groups = q4.deduplicate_reviews(records)

    assert len(groups) == 2
    assert len(groups[0].records) == 2
    assert groups[0].representative_raw_text == "Não recebi o produto."


def test_contains_evidence_requires_original_portuguese_fragment() -> None:
    raw_text = "Não recebi o produto."

    assert q4.contains_evidence(raw_text, "Não recebi o produto")
    assert not q4.contains_evidence(raw_text, "Nao recebi o produto")


def test_provider_config_requires_openrouter_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        q4.provider_config("openrouter")


def test_provider_config_base_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")

    openrouter = q4.provider_config("openrouter")
    deepseek = q4.provider_config("deepseek")

    assert openrouter.base_url == q4.OPENROUTER_BASE_URL
    assert openrouter.default_headers is not None
    assert deepseek.base_url == q4.DEEPSEEK_BASE_URL
    assert deepseek.default_headers is None


def test_live_sample_covers_rule_small_and_large() -> None:
    items = [
        *(routed(f"ruim {i}", "rule", f"r{i}") for i in range(12)),
        *(routed(f"small text {i}", "small_llm", f"s{i}") for i in range(12)),
        *(routed(f"large text {i}", "large_llm", f"l{i}") for i in range(12)),
    ]

    sampled = q4.live_sample_routed_groups(items, live_sample_size=30)
    counts = {}
    for item in sampled:
        counts[item.route] = counts.get(item.route, 0) + 1

    assert len(sampled) == 30
    assert counts == {"rule": 10, "small_llm": 10, "large_llm": 10}


def test_live_sample_zero_means_full_live() -> None:
    items = [
        routed("small one", "small_llm", "s1"),
        routed("large one", "large_llm", "l1"),
    ]

    assert q4.live_sample_routed_groups(items, live_sample_size=0) == items


def test_large_prompt_satisfies_json_mode_requirement(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}
    extractor = object.__new__(q4.CompatibleLLMExtractor)
    extractor.large_model = "deepseek-v4-pro"

    def fake_chat_json(model: str, system_prompt: str, user_prompt: str) -> q4.LLMJsonResponse:
        captured["model"] = model
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return q4.LLMJsonResponse(
            text=json.dumps(
                {
                    "issues": [
                        {
                            "category": "delivery",
                            "subcategory": "not_received",
                            "evidence": "Produto não entregue",
                            "confidence": 0.9,
                        }
                    ],
                    "needs_manual_review": False,
                }
            ),
            usage=q4.ProviderUsage(input_tokens=1, output_tokens=1),
        )

    monkeypatch.setattr(extractor, "_chat_json", fake_chat_json)

    result, _usage = extractor.call_large_single(make_group("Produto não entregue"))

    assert captured["model"] == "deepseek-v4-pro"
    assert "json" in captured["system_prompt"].lower()
    assert result.method == "large_llm"


def test_schema_failure_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeExtractor:
        def __init__(self, **_: object) -> None:
            pass

        def call_small_batch(self, batch: list[q4.DedupGroup]) -> tuple[dict[str, q4.ExtractionResult], q4.ProviderUsage]:
            raise json.JSONDecodeError("bad", "", 0)

        def call_large_single(self, group: q4.DedupGroup) -> tuple[q4.ExtractionResult, q4.ProviderUsage]:
            raise json.JSONDecodeError("bad", "", 0)

    monkeypatch.setattr(q4, "CompatibleLLMExtractor", FakeExtractor)
    groups = [routed("produto chegou quebrado", "small_llm", "s1")]

    results, _cost, stats, _active = q4.process_routed_groups(
        routed_groups=groups,
        mode="live",
        provider="openrouter",
        small_model="deepseek/deepseek-v3.1",
        large_model="deepseek/deepseek-r1",
        batch_token_budget=6000,
        max_cost_usd=1.0,
        live_sample_size=None,
    )

    assert results["s1"].method == "offline_large_llm_fallback"
    assert stats.failed_llm_count == 2
    assert stats.schema_error_count == 2


def test_cost_gate_stops_live_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeExtractor:
        def __init__(self, **_: object) -> None:
            pass

        def call_small_batch(self, batch: list[q4.DedupGroup]) -> tuple[dict[str, q4.ExtractionResult], q4.ProviderUsage]:
            raise AssertionError("budget gate should prevent this call")

    monkeypatch.setattr(q4, "CompatibleLLMExtractor", FakeExtractor)
    groups = [routed("produto chegou quebrado", "small_llm", "s1")]

    results, _cost, stats, _active = q4.process_routed_groups(
        routed_groups=groups,
        mode="live",
        provider="openrouter",
        small_model="deepseek/deepseek-v3.1",
        large_model="deepseek/deepseek-r1",
        batch_token_budget=6000,
        max_cost_usd=0.000001,
        live_sample_size=None,
    )

    assert results["s1"].method == "offline_small_llm_fallback"
    assert stats.budget_exhausted is True
    assert stats.llm_call_count == 0


def test_no_cost_limit_allows_expensive_estimate() -> None:
    tracker = q4.CostTracker(max_cost_usd=None)

    updated = tracker.add_call("large", input_tokens=10_000_000, output_tokens=10_000_000)

    assert updated.estimated_cost_usd > 0
    assert updated.max_cost_usd is None
