"""Sync token pricing from LangSmith model-price-map into local YAML."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
import yaml

from dubai.model_pricing import (
    PricingRates,
    default_pricing_path,
    load_model_pricing,
    seed_pricing_cache,
)
from dubai.settings import get_settings

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_PROBES_PATH = _PACKAGE_DIR.parent / "config" / "langsmith_pricing_probes.yaml"
_LANGSMITH_PRICE_MAP_URL = "https://api.smith.langchain.com/api/v1/model-price-map"

_SYNC_DONE = False


def default_probes_path() -> Path:
    settings = get_settings()
    if settings.langsmith_pricing_probes_path:
        return Path(settings.langsmith_pricing_probes_path).expanduser()
    return _DEFAULT_PROBES_PATH


def fetch_langsmith_model_price_map(*, api_key: str) -> list[dict[str, Any]]:
    """Return LangSmith tenant model price map entries."""
    response = requests.get(
        _LANGSMITH_PRICE_MAP_URL,
        headers={"X-API-Key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("unexpected model-price-map payload")
    return payload


def match_langsmith_entry(
    probe: str, entries: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """First price-map row whose match_pattern regex matches ``probe``."""
    for entry in entries:
        pattern = entry.get("match_pattern")
        if not isinstance(pattern, str):
            continue
        try:
            if re.match(pattern, probe):
                return entry
        except re.error:
            continue
    return None


def rates_from_langsmith_entry(entry: dict[str, Any]) -> PricingRates:
    """LangSmith stores USD per token; we use USD per 1K tokens."""
    prompt = float(entry["prompt_cost"])
    completion = float(entry["completion_cost"])
    return PricingRates(input_per_1k=prompt * 1000.0, output_per_1k=completion * 1000.0)


def load_pricing_probes(*, path: Path | None = None) -> dict[str, str]:
    resolved = path or default_probes_path()
    if not resolved.is_file():
        logger.warning("LangSmith pricing probes file not found: %s", resolved)
        return {}
    with resolved.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"probes file must be a mapping: {resolved}")
    return {str(k): str(v) for k, v in payload.items()}


def build_synced_pricing_table(
    *,
    model_ids: list[str],
    entries: list[dict[str, Any]],
    probes: dict[str, str],
    base_table: dict[str, PricingRates],
) -> tuple[dict[str, PricingRates], list[str]]:
    """Merge LangSmith prices into ``base_table`` for configured models."""
    merged = dict(base_table)
    updated: list[str] = []
    for model_id in model_ids:
        probe = probes.get(model_id)
        if not probe:
            continue
        entry = match_langsmith_entry(probe, entries)
        if entry is None:
            logger.info(
                "No LangSmith price-map match for model_id=%r probe=%r",
                model_id,
                probe,
            )
            continue
        merged[model_id] = rates_from_langsmith_entry(entry)
        updated.append(model_id)
    return merged, updated


def write_pricing_yaml(path: Path, table: dict[str, PricingRates]) -> None:
    """Persist pricing table (LangSmith-synced values overwrite prior rows)."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"# USD per 1,000 tokens.\n"
        f"# Partially synced from LangSmith model-price-map at {stamp}.\n"
        f"# Re-sync: SYNC_LANGSMITH_PRICING=true on API startup.\n\n"
    )
    body = {
        model_id: {
            "input_per_1k": rates.input_per_1k,
            "output_per_1k": rates.output_per_1k,
        }
        for model_id, rates in sorted(table.items())
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(header)
        yaml.safe_dump(body, handle, sort_keys=False, default_flow_style=False)


def sync_pricing_from_langsmith(
    model_ids: list[str],
    *,
    write_yaml: bool | None = None,
) -> list[str]:
    """Fetch LangSmith prices and merge into local pricing. Returns updated ids."""
    settings = get_settings()
    api_key = settings.langchain_api_key
    if not api_key:
        logger.info("Skipping LangSmith pricing sync — no LANGCHAIN_API_KEY")
        return []

    entries = fetch_langsmith_model_price_map(api_key=api_key)
    probes = load_pricing_probes()
    pricing_path = default_pricing_path()
    base_table = load_model_pricing(path=pricing_path)
    merged, updated = build_synced_pricing_table(
        model_ids=model_ids,
        entries=entries,
        probes=probes,
        base_table=base_table,
    )

    should_write = (
        settings.sync_langsmith_pricing_write if write_yaml is None else write_yaml
    )
    if should_write and updated:
        write_pricing_yaml(pricing_path, merged)

    if updated:
        seed_pricing_cache(merged, path=pricing_path)

    return updated


def maybe_sync_pricing_from_langsmith(model_ids: list[str]) -> None:
    """Run once per process when SYNC_LANGSMITH_PRICING is enabled."""
    global _SYNC_DONE
    if _SYNC_DONE:
        return
    _SYNC_DONE = True

    settings = get_settings()
    if not settings.sync_langsmith_pricing:
        return

    try:
        updated = sync_pricing_from_langsmith(model_ids)
    except Exception as error:  # noqa: BLE001
        logger.warning("LangSmith pricing sync failed: %s", error)
        return

    if updated:
        logger.info(
            "LangSmith pricing sync updated %d models: %s",
            len(updated),
            ", ".join(updated),
        )
    else:
        logger.info("LangSmith pricing sync completed — no model prices updated")
