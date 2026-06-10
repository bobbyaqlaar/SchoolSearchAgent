"""Load per-model token pricing from YAML (config/model_pricing.yaml by default)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from dubai.settings import get_settings

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_PRICING_PATH = _PACKAGE_DIR.parent / "config" / "model_pricing.yaml"

_CACHE: dict[str, "PricingRates"] | None = None
_CACHE_PATH: Path | None = None


@dataclass(frozen=True)
class PricingRates:
    """USD per 1,000 tokens."""

    input_per_1k: float
    output_per_1k: float


def default_pricing_path() -> Path:
    settings = get_settings()
    if settings.model_pricing_path:
        return Path(settings.model_pricing_path).expanduser()
    return _DEFAULT_PRICING_PATH


def clear_pricing_cache() -> None:
    """Reset cached pricing (for tests and hot reload)."""
    global _CACHE, _CACHE_PATH
    _CACHE = None
    _CACHE_PATH = None


def seed_pricing_cache(
    table: dict[str, PricingRates], *, path: Path | None = None
) -> None:
    """Inject pricing table into the process cache (e.g. after LangSmith sync)."""
    global _CACHE, _CACHE_PATH
    resolved = path or default_pricing_path()
    _CACHE = dict(table)
    _CACHE_PATH = resolved


def _parse_rates(raw: Any) -> PricingRates:
    if not isinstance(raw, dict):
        raise ValueError("each model entry must be a mapping")
    if "input_per_1k" not in raw or "output_per_1k" not in raw:
        raise ValueError("pricing entry requires input_per_1k and output_per_1k")
    return PricingRates(
        input_per_1k=float(raw["input_per_1k"]),
        output_per_1k=float(raw["output_per_1k"]),
    )


def load_model_pricing(*, path: Path | None = None) -> dict[str, PricingRates]:
    """Load the full pricing table from YAML."""
    global _CACHE, _CACHE_PATH
    resolved = path or default_pricing_path()
    if _CACHE is not None and _CACHE_PATH == resolved:
        return _CACHE

    if not resolved.is_file():
        raise FileNotFoundError(f"model pricing file not found: {resolved}")

    with resolved.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"model pricing file must be a mapping: {resolved}")

    table: dict[str, PricingRates] = {}
    for model_id, raw in payload.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model ids must be non-empty strings")
        table[model_id] = _parse_rates(raw)

    _CACHE = table
    _CACHE_PATH = resolved
    return table


def get_model_pricing(model_id: str) -> PricingRates:
    """Return pricing for ``model_id``, or zero rates if not configured."""
    try:
        return load_model_pricing()[model_id]
    except KeyError:
        logger.info("No pricing entry for model_id=%s; using zero rates", model_id)
        return PricingRates(0.0, 0.0)


def warn_missing_registry_pricing(model_ids: list[str]) -> None:
    """Log models registered for routing but absent from the pricing file."""
    try:
        table = load_model_pricing()
    except OSError as error:
        logger.warning("Could not load model pricing: %s", error)
        return
    for model_id in model_ids:
        if model_id not in table:
            logger.warning(
                "Model %r is in MODEL_REGISTRY but missing from %s",
                model_id,
                _CACHE_PATH,
            )
