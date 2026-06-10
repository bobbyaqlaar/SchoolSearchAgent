"""LangSmith evaluation suites for the KHDA platform.

- `eval_parsing` (primary): open-data parsing regression via the production parser.
- `eval_qa` (secondary, manual): chat-agent semantic match (graph-backed tool).
"""

from evals.datasets import (
    EXTRACTION_DATASET,
    LANGSMITH_DATASETS,
    QA_DATASET,
    ensure_seed_examples,
    sync_dataset,
)
from evals.eval_parsing import (
    fee_count_accuracy,
    no_negative_fees,
    regression_pass,
    schema_valid,
    target_parsing_runner,
)

__all__ = [
    "EXTRACTION_DATASET",
    "QA_DATASET",
    "LANGSMITH_DATASETS",
    "sync_dataset",
    "ensure_seed_examples",
    "target_parsing_runner",
    "regression_pass",
    "no_negative_fees",
    "schema_valid",
    "fee_count_accuracy",
    "semantic_match",
]


def __getattr__(name: str):
    if name == "semantic_match":
        from evals.eval_qa import semantic_match

        return semantic_match
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
