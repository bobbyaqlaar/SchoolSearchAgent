"""Token and cost accounting (README real-time evaluation constraint 2).

Pricing is read from ``config/model_pricing.yaml`` via ``dubai.model_pricing``.
Token counts are captured through a LangChain callback so node/agent code never
hand-parses provider metadata; adding providers needs zero changes here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from dubai.model_pricing import get_model_pricing

logger = logging.getLogger(__name__)


@dataclass
class ModelUsage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class CostTracker:
    usage: dict[str, ModelUsage] = field(default_factory=dict)

    def record(self, model_id: str, input_tokens: int, output_tokens: int) -> None:
        rates = get_model_pricing(model_id)
        in_price, out_price = rates.input_per_1k, rates.output_per_1k

        entry = self.usage.setdefault(model_id, ModelUsage(model=model_id))
        entry.input_tokens += input_tokens
        entry.output_tokens += output_tokens
        entry.cost_usd += input_tokens / 1000 * in_price + output_tokens / 1000 * out_price

    @property
    def total_cost(self) -> float:
        return sum(entry.cost_usd for entry in self.usage.values())

    def summary(self) -> dict[str, ModelUsage]:
        return dict(self.usage)

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """JSON-serializable view for the API envelope."""
        return {
            model_id: {
                "model": entry.model,
                "input_tokens": entry.input_tokens,
                "output_tokens": entry.output_tokens,
                "cost_usd": round(entry.cost_usd, 6),
            }
            for model_id, entry in self.usage.items()
        }

    def as_callback(self, model_id: str) -> BaseCallbackHandler:
        """Return a callback that records token usage for ``model_id``."""
        return _CostCallback(self, model_id)


class _CostCallback(BaseCallbackHandler):
    def __init__(self, tracker: CostTracker, model_id: str):
        self._tracker = tracker
        self._model_id = model_id

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:  # noqa: ANN401
        input_tokens, output_tokens = _extract_token_counts(response)
        self._tracker.record(self._model_id, input_tokens, output_tokens)


def _extract_token_counts(response: Any) -> tuple[int, int]:  # noqa: ANN401
    try:
        output = getattr(response, "llm_output", None) or {}
        token_usage = output.get("token_usage") or output.get("usage") or {}
        if token_usage:
            return (
                int(token_usage.get("prompt_tokens", 0)),
                int(token_usage.get("completion_tokens", 0)),
            )
        for generations in getattr(response, "generations", []) or []:
            for generation in generations:
                message = getattr(generation, "message", None)
                usage = getattr(message, "usage_metadata", None)
                if usage:
                    return int(usage.get("input_tokens", 0)), int(
                        usage.get("output_tokens", 0)
                    )
    except Exception as error:  # noqa: BLE001
        logger.debug("Could not extract token counts: %s", error)
    return 0, 0
