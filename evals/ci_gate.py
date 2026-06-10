"""CI gate: fail the process when LangSmith eval scores drop below thresholds."""

from __future__ import annotations

import sys
from typing import Any

REQUIRED_EVALUATORS: tuple[str, ...] = (
    "regression_pass",
    "no_negative_fees",
    "schema_valid",
)
MIN_BINARY_SCORE = 1.0
MIN_FEE_COUNT_SCORE = 0.75


def _column_for_evaluator(columns: list[str], evaluator: str) -> str | None:
    if evaluator in columns:
        return evaluator
    prefixed = f"feedback.{evaluator}"
    if prefixed in columns:
        return prefixed
    for col in columns:
        if col.endswith(evaluator):
            return col
    return None


def scores_from_experiment(experiment_results: Any) -> dict[str, float]:
    """Mean evaluator scores from an evaluate() ExperimentResults object."""
    if not hasattr(experiment_results, "to_pandas"):
        raise ValueError("experiment_results must expose to_pandas()")

    frame = experiment_results.to_pandas()
    if frame.empty:
        raise ValueError("experiment produced no rows")

    columns = [str(c) for c in frame.columns]
    scores: dict[str, float] = {}
    for evaluator in (*REQUIRED_EVALUATORS, "fee_count_accuracy"):
        col = _column_for_evaluator(columns, evaluator)
        if col is None:
            continue
        series = frame[col].dropna()
        if len(series) == 0:
            continue
        scores[evaluator] = float(series.mean())
    return scores


def enforce_eval_scores(
    experiment_results: Any,
    *,
    min_binary: float = MIN_BINARY_SCORE,
    min_fee_count: float = MIN_FEE_COUNT_SCORE,
) -> None:
    """Exit with code 1 when required evaluators score below threshold."""
    scores = scores_from_experiment(experiment_results)
    failures: list[str] = []

    for key in REQUIRED_EVALUATORS:
        if key not in scores:
            failures.append(f"{key}: missing")
            continue
        if scores[key] < min_binary:
            failures.append(f"{key}: {scores[key]:.3f} < {min_binary}")

    if "fee_count_accuracy" in scores and scores["fee_count_accuracy"] < min_fee_count:
        failures.append(
            f"fee_count_accuracy: {scores['fee_count_accuracy']:.3f} < {min_fee_count}"
        )

    if failures:
        print("Eval CI gate FAILED:")
        for line in failures:
            print(f"  - {line}")
        print("Aggregated scores:", scores)
        raise SystemExit(1)

    print("Eval CI gate PASSED:", scores)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    print("ci_gate.main is invoked from eval_parsing, not standalone.", file=sys.stderr)
    return 2
