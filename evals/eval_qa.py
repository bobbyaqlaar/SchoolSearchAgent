"""SECONDARY eval (manual/nightly): Ask agent semantic match + scope guard evaluators.

Scores answers by cosine similarity vs reference and runs deterministic guard
evaluators from ``evals/ask_evaluators.py``. Excluded from CI (cost + rate limits).

Usage:
  uv run python -m evals.eval_qa              # LangSmith experiment (needs valid key)
  uv run python -m evals.eval_qa --local      # run QA_SEED locally, no LangSmith
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from dashboard_queries import DubaiDashboardEngine
from dubai.ask_agent import run_ask
from dubai.cost_tracker import CostTracker
from dubai.settings import get_settings
from evals.ask_evaluators import (
    foreign_location_must_refuse,
    invalid_fee_term_refusal_when_required,
    jurisdiction_refusal_when_required,
    no_false_jurisdiction_refusal,
)
from dubai.text import cosine_similarity

DEFAULT_QA_MODEL = "github:gpt-4o-mini"

_qa_engine: DubaiDashboardEngine | None = None


def _engine_for_qa() -> DubaiDashboardEngine:
    global _qa_engine  # noqa: PLW0603
    if _qa_engine is None:
        settings = get_settings()
        _qa_engine = DubaiDashboardEngine(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
    return _qa_engine


def semantic_match(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    if not outputs or "answer" not in outputs:
        return {
            "key": "semantic_match",
            "score": 0.0,
            "comment": "No answer produced (likely an upstream LLM/API error).",
        }
    try:
        score = cosine_similarity(reference_outputs["answer"], outputs["answer"])
    except ImportError:
        return {
            "key": "semantic_match",
            "score": 0.0,
            "comment": "sentence-transformers not installed — run: uv sync --extra evals",
        }
    return {"key": "semantic_match", "score": float(score)}


def target(inputs: dict[str, Any]) -> dict[str, Any]:
    time.sleep(2)  # pace requests for free-tier rate limits
    result = run_ask(
        str(inputs["question"]),
        model_id=DEFAULT_QA_MODEL,
        db=_engine_for_qa(),
        cost_tracker=CostTracker(),
    )
    return {"answer": result.answer}


def _require_semantic_deps() -> None:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        print(
            "QA semantic_match requires optional eval dependencies.\n"
            "Install with: uv sync --extra evals\n"
            "Then re-run: uv run python -m evals.eval_qa",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


def _evaluators() -> list[Any]:
    return [
        semantic_match,
        no_false_jurisdiction_refusal,
        jurisdiction_refusal_when_required,
        foreign_location_must_refuse,
        invalid_fee_term_refusal_when_required,
    ]


def run_local_eval(*, examples: list[dict[str, Any]] | None = None) -> int:
    """Run QA evaluators against seed examples without LangSmith."""
    from evals.datasets import QA_SEED

    rows = examples if examples is not None else QA_SEED
    failures = 0
    print(f"Running local QA eval on {len(rows)} examples…")
    for example in rows:
        question = str(example["inputs"].get("question", ""))
        print(f"\n— {question}")
        try:
            outputs = target(example["inputs"])
        except Exception as error:  # noqa: BLE001
            outputs = {"answer": ""}
            print(f"  target error: {error}")
        for evaluator in _evaluators():
            if evaluator is semantic_match:
                result = evaluator(outputs, example["outputs"])
            else:
                result = evaluator(outputs, example["outputs"], example["inputs"])
            status = "PASS" if result["score"] >= 1.0 else "FAIL"
            print(f"  [{status}] {result['key']}: {result['score']:.2f} — {result.get('comment', '')}")
            if result["score"] < 1.0:
                failures += 1
    print(f"\nLocal QA eval complete — {failures} failing checks.")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="KHDA Ask/Q&A eval")
    parser.add_argument(
        "--local",
        action="store_true",
        help="run QA_SEED locally without LangSmith (no cloud dataset sync)",
    )
    args = parser.parse_args(argv)

    if args.local:
        _require_semantic_deps()
        raise SystemExit(run_local_eval())

    _require_semantic_deps()

    try:
        from langsmith.evaluation import evaluate
        from langsmith.utils import LangSmithAuthError

        from evals.datasets import QA_DATASET, QA_SEED, ensure_seed_examples
    except ImportError as error:
        print(f"LangSmith packages unavailable: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    try:
        ensure_seed_examples(QA_DATASET, QA_SEED)
    except LangSmithAuthError:
        print(
            "LangSmith authentication failed (401). Check LANGCHAIN_API_KEY in .env — "
            "only one key should be set, and it must be a valid ls__ token from "
            "https://smith.langchain.com/settings.\n"
            "Tip: run without LangSmith: uv run python -m evals.eval_qa --local",
            file=sys.stderr,
        )
        raise SystemExit(1)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    evaluate(
        target,
        data=QA_DATASET,
        evaluators=[
            semantic_match,
            no_false_jurisdiction_refusal,
            jurisdiction_refusal_when_required,
        ],
        experiment_prefix=f"qa-{timestamp}",
        max_concurrency=1,
    )


if __name__ == "__main__":
    main()
