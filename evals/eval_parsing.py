"""PRIMARY eval: open-data parsing quality.

Runs the production Excel parser (`parse_source_to_school`) so eval matches sync.
Evaluators are pure functions (unit-testable without LangSmith); LangSmith wiring
lives in `main`.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any

from dubai.data_sources import parse_source_to_school
from dubai.schemas import SchoolDataModel


def target_parsing_runner(inputs: dict[str, Any], *, model_id: str = "n/a") -> dict[str, Any]:
    """Same code path as production sync parsing."""
    _ = model_id
    source = inputs.get("source")
    if source is None:
        raise ValueError("eval inputs must include a registry `source` dict")
    result: SchoolDataModel = parse_source_to_school(source)
    return {
        "fees_count": len(result.fees),
        "has_neighborhood": bool(result.neighborhood),
        "fees": [f.model_dump() for f in result.fees],
        "neighborhood": result.neighborhood,
    }


def regression_pass(outputs: dict[str, Any]) -> dict[str, Any]:
    passed = outputs.get("fees_count", 0) > 0 and bool(outputs.get("has_neighborhood"))
    return {"key": "regression_pass", "score": 1.0 if passed else 0.0}


def no_negative_fees(outputs: dict[str, Any]) -> dict[str, Any]:
    fees = outputs.get("fees", [])
    ok = all(float(f.get("tuition_fee", 0)) > 0 for f in fees) if fees else False
    return {"key": "no_negative_fees", "score": 1.0 if ok else 0.0}


def schema_valid(outputs: dict[str, Any]) -> dict[str, Any]:
    try:
        SchoolDataModel(
            school_id="x",
            name="x",
            neighborhood=outputs.get("neighborhood", "") or "x",
            fees=outputs.get("fees", []),
        )
        return {"key": "schema_valid", "score": 1.0}
    except Exception:  # noqa: BLE001
        return {"key": "schema_valid", "score": 0.0}


def fee_count_accuracy(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    if "expected_fee_count" not in reference_outputs:
        return {
            "key": "fee_count_accuracy",
            "score": 1.0,
            "comment": "skipped — runtime example without label",
        }
    expected = int(reference_outputs.get("expected_fee_count", 0)) or 1
    extracted = int(outputs.get("fees_count", 0))
    return {"key": "fee_count_accuracy", "score": min(extracted, expected) / expected}


def main() -> None:
    parser = argparse.ArgumentParser(description="KHDA open-data parsing eval (LangSmith)")
    parser.add_argument(
        "--skip-ci-gate",
        action="store_true",
        help="do not exit non-zero when eval scores fail (local debugging)",
    )
    args = parser.parse_args()

    from langsmith.evaluation import evaluate

    from evals.ci_gate import enforce_eval_scores
    from evals.datasets import EXTRACTION_DATASET, EXTRACTION_SEED, ensure_seed_examples

    ensure_seed_examples(EXTRACTION_DATASET, EXTRACTION_SEED)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    experiment_results = evaluate(
        lambda inputs: target_parsing_runner(inputs),
        data=EXTRACTION_DATASET,
        evaluators=[regression_pass, no_negative_fees, schema_valid, fee_count_accuracy],
        experiment_prefix=f"open-data-parse-{timestamp}",
    )
    print(f"Done — {getattr(experiment_results, 'url', experiment_results)}")
    if not args.skip_ci_gate:
        enforce_eval_scores(experiment_results)


if __name__ == "__main__":
    main()
