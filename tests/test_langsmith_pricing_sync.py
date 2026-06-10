"""Tests for LangSmith model-price-map sync."""

from __future__ import annotations

from pathlib import Path

import pytest

from dubai.langsmith_pricing_sync import (
    build_synced_pricing_table,
    match_langsmith_entry,
    rates_from_langsmith_entry,
    sync_pricing_from_langsmith,
)
from dubai.model_pricing import (
    PricingRates,
    clear_pricing_cache,
    get_model_pricing,
    load_model_pricing,
)


def test_match_langsmith_entry():
    entries = [
        {"match_pattern": r"^gpt-4o$", "prompt_cost": 0.0000025, "completion_cost": 0.00001},
        {"match_pattern": r"^gpt-4o-mini$", "prompt_cost": 0.00000015, "completion_cost": 0.0000006},
    ]
    assert match_langsmith_entry("gpt-4o", entries) == entries[0]
    assert match_langsmith_entry("unknown", entries) is None


def test_rates_from_langsmith_entry():
    rates = rates_from_langsmith_entry(
        {"prompt_cost": 0.0000025, "completion_cost": 0.00001}
    )
    assert rates == PricingRates(input_per_1k=0.0025, output_per_1k=0.01)


def test_build_synced_pricing_table_merges_matched_only():
    base = {"gpt-4o": PricingRates(0.0, 0.0)}
    entries = [
        {"match_pattern": r"^gpt-4o$", "prompt_cost": 0.0000025, "completion_cost": 0.00001},
    ]
    probes = {"gpt-4o": "gpt-4o", "missing": "nope"}
    merged, updated = build_synced_pricing_table(
        model_ids=["gpt-4o", "missing"],
        entries=entries,
        probes=probes,
        base_table=base,
    )
    assert updated == ["gpt-4o"]
    assert merged["gpt-4o"] == PricingRates(0.0025, 0.01)


def test_sync_pricing_from_langsmith_in_memory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    clear_pricing_cache()
    pricing_path = tmp_path / "model_pricing.yaml"
    pricing_path.write_text(
        "gpt-4o:\n  input_per_1k: 0.0\n  output_per_1k: 0.0\n",
        encoding="utf-8",
    )
    probes_path = tmp_path / "probes.yaml"
    probes_path.write_text("gpt-4o: gpt-4o\n", encoding="utf-8")

    monkeypatch.setenv("MODEL_PRICING_PATH", str(pricing_path))
    monkeypatch.setenv("LANGSMITH_PRICING_PROBES_PATH", str(probes_path))
    monkeypatch.setenv("LANGCHAIN_API_KEY", "test-key")

    def fake_fetch(*, api_key: str):
        assert api_key == "test-key"
        return [
            {
                "match_pattern": r"^gpt-4o$",
                "prompt_cost": 0.0000025,
                "completion_cost": 0.00001,
            }
        ]

    monkeypatch.setattr(
        "dubai.langsmith_pricing_sync.fetch_langsmith_model_price_map",
        fake_fetch,
    )

    updated = sync_pricing_from_langsmith(["gpt-4o"], write_yaml=False)
    assert updated == ["gpt-4o"]
    assert get_model_pricing("gpt-4o") == PricingRates(0.0025, 0.01)
    assert pricing_path.read_text(encoding="utf-8").startswith("gpt-4o:")


def test_sync_pricing_from_langsmith_writes_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    clear_pricing_cache()
    pricing_path = tmp_path / "model_pricing.yaml"
    pricing_path.write_text(
        "gpt-4o:\n  input_per_1k: 0.0\n  output_per_1k: 0.0\n",
        encoding="utf-8",
    )
    probes_path = tmp_path / "probes.yaml"
    probes_path.write_text("gpt-4o: gpt-4o\n", encoding="utf-8")

    monkeypatch.setenv("MODEL_PRICING_PATH", str(pricing_path))
    monkeypatch.setenv("LANGSMITH_PRICING_PROBES_PATH", str(probes_path))
    monkeypatch.setenv("LANGCHAIN_API_KEY", "test-key")

    monkeypatch.setattr(
        "dubai.langsmith_pricing_sync.fetch_langsmith_model_price_map",
        lambda *, api_key: [
            {
                "match_pattern": r"^gpt-4o$",
                "prompt_cost": 0.0000025,
                "completion_cost": 0.00001,
            }
        ],
    )

    updated = sync_pricing_from_langsmith(["gpt-4o"], write_yaml=True)
    assert updated == ["gpt-4o"]
    table = load_model_pricing(path=pricing_path)
    assert table["gpt-4o"] == PricingRates(0.0025, 0.01)
    assert "LangSmith" in pricing_path.read_text(encoding="utf-8")
