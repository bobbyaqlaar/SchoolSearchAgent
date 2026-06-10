"""Single authority for LangSmith dataset names + idempotent sync.

Seed examples are upserted without deleting runtime failure rows appended during
production sync runs.
"""

from __future__ import annotations

import hashlib
from typing import Any

from dubai.ask_prompt import JURISDICTION_REFUSAL

EXTRACTION_DATASET = "dubai_extraction_failures"
QA_DATASET = "dubai_qa"

LANGSMITH_DATASETS: list[str] = [EXTRACTION_DATASET, QA_DATASET]

RUNTIME_SOURCE = "runtime"
SEED_SOURCE = "seed"

# Seed hard fee-table cases. Runtime validation/extraction failures append via
# `append_failure_example` and are never removed by seed sync.
EXTRACTION_SEED: list[dict[str, Any]] = [
    {
        "inputs": {
            "source": {
                "school_id": "horizons-english-school",
                "school_name": "Horizons English School",
                "hash": "seed-horizons",
                "document_text": "seed",
                "raw_payload": {
                    "academic_year": "2024-2025",
                    "name": "Horizons English School",
                    "neighborhood": "Al Wasl",
                    "curriculums": ["UK"],
                    "khda_rating": "Very Good",
                    "fees": [
                        {"grade": "FS1", "tuition_fee": 42000.0},
                        {"grade": "FS2", "tuition_fee": 42000.0},
                        {"grade": "YEAR 1", "tuition_fee": 50000.0},
                        {"grade": "YEAR 2", "tuition_fee": 50000.0},
                    ],
                },
            }
        },
        "outputs": {
            "expected_fee_count": 4,
            "has_neighborhood": True,
            "source": SEED_SOURCE,
        },
    },
    {
        "inputs": {
            "source": {
                "school_id": "gems-modern-academy",
                "school_name": "GEMS Modern Academy",
                "hash": "seed-gems",
                "document_text": "seed",
                "raw_payload": {
                    "academic_year": "2024-2025",
                    "name": "GEMS Modern Academy",
                    "neighborhood": "Nad Al Sheba",
                    "curriculums": ["Indian"],
                    "khda_rating": "Outstanding",
                    "fees": [
                        {"grade": "KG1", "tuition_fee": 30000.0},
                        {"grade": "KG2", "tuition_fee": 30000.0},
                        {"grade": "GRADE 1", "tuition_fee": 35000.0},
                        {"grade": "GRADE 12", "tuition_fee": 60000.0},
                    ],
                },
            }
        },
        "outputs": {
            "expected_fee_count": 4,
            "has_neighborhood": True,
            "source": SEED_SOURCE,
        },
    },
]

QA_SEED: list[dict[str, Any]] = [
    {
        "inputs": {"question": "What KHDA rating did GEMS Wellington receive?"},
        "outputs": {"answer": "GEMS Wellington holds an Outstanding KHDA rating."},
    },
    {
        "inputs": {"question": "What is the capital of France?"},
        "outputs": {"answer": JURISDICTION_REFUSAL},
    },
    {
        "inputs": {
            "question": "Which Outstanding Dubai schools offer UK curriculum under AED 90000?",
        },
        "outputs": {
            "answer": "Outstanding Dubai private schools offering UK curriculum under AED 90,000 include several matches from the KHDA graph.",
        },
    },
    {
        "inputs": {
            "question": "Indian curriculum schools with Very Good rating and budget below 60000 AED",
        },
        "outputs": {
            "answer": "Indian curriculum schools in Dubai with Very Good rating under AED 60,000 include matches from the KHDA graph.",
        },
    },
    {
        "inputs": {
            "question": "US curriculum schools in Mirdif under 70000",
        },
        "outputs": {
            "answer": "US curriculum schools in Mirdif under AED 70,000 include matches from the KHDA graph.",
        },
    },
    {
        "inputs": {
            "question": "Australian curriculum Outstanding schools under AED 85000",
        },
        "outputs": {
            "answer": "Outstanding Dubai schools offering Australian curriculum under AED 85,000 include matches from the KHDA graph.",
        },
    },
    {
        "inputs": {
            "question": "UK schools with fees greater than 70000 AED",
        },
        "outputs": {
            "answer": "UK curriculum Dubai private schools whose lowest annual tuition exceeds AED 70,000 include matches from the KHDA graph.",
        },
    },
    {
        "inputs": {
            "question": "Schools of UK with rent less than 70000",
        },
        "outputs": {
            "answer": "Sorry, I can only search KHDA annual tuition fees and budgets in AED — not rent or housing charges.",
        },
    },
    {
        "inputs": {
            "question": "Schools in UK with rent less than 70000",
        },
        "outputs": {
            "answer": "Sorry, I can only search KHDA annual tuition fees and budgets in AED — not rent or housing charges.",
        },
    },
    {
        "inputs": {
            "question": "Schools in UK under 70000 AED fees",
        },
        "outputs": {
            "answer": "Sorry, my jurisdiction is limited to the Dubai Emirate of UAE.",
        },
    },
]


def example_key(inputs: dict[str, Any]) -> str:
    """Stable dedupe key for dataset rows."""
    if failure_key := inputs.get("failure_key"):
        return str(failure_key)
    source = inputs.get("source")
    if isinstance(source, dict):
        return str(source.get("school_id") or source.get("school_name") or "")
    return str(inputs.get("question") or inputs.get("document_text", ""))


def failure_key_for(school_id: str, source_hash: str) -> str:
    return f"{school_id}:{source_hash}"


def document_fingerprint(document_text: str) -> str:
    normalized = document_text.strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def sync_dataset(name: str, examples: list[dict[str, Any]], *, client: Any = None) -> None:
    """Create-if-missing + drift-detect + upsert examples (QA-sized sets only)."""
    if client is None:
        from langsmith import Client

        client = Client()

    if not client.has_dataset(dataset_name=name):
        client.create_dataset(dataset_name=name)

    dataset = client.read_dataset(dataset_name=name)
    existing = list(client.list_examples(dataset_id=dataset.id))
    desired_by_key = {example_key(ex["inputs"]): ex for ex in examples}
    by_key = {example_key(ex.inputs): ex for ex in existing}

    if set(desired_by_key) == set(by_key) and all(
        dict(by_key[key].outputs or {}) == desired_by_key[key].get("outputs", {})
        for key in desired_by_key
    ):
        return

    for key, current in by_key.items():
        if key not in desired_by_key:
            client.delete_example(example_id=current.id)

    for key, seed in desired_by_key.items():
        current = by_key.get(key)
        if current is None:
            client.create_examples(dataset_name=name, examples=[seed])
            continue
        if dict(current.outputs or {}) == seed.get("outputs", {}):
            continue
        client.delete_example(example_id=current.id)
        client.create_examples(dataset_name=name, examples=[seed])


def ensure_seed_examples(
    name: str,
    seed_examples: list[dict[str, Any]],
    *,
    client: Any = None,
) -> None:
    """Upsert in-code seed rows; preserve runtime-appended examples."""
    if client is None:
        from langsmith import Client

        client = Client()

    if not client.has_dataset(dataset_name=name):
        client.create_dataset(dataset_name=name)

    dataset = client.read_dataset(dataset_name=name)
    existing = list(client.list_examples(dataset_id=dataset.id))
    by_key = {example_key(ex.inputs): ex for ex in existing}

    for seed in seed_examples:
        key = example_key(seed["inputs"])
        current = by_key.get(key)
        if current is None:
            client.create_examples(dataset_name=name, examples=[seed])
            continue
        current_outputs = dict(current.outputs or {})
        if current_outputs == seed.get("outputs", {}):
            continue
        client.delete_example(example_id=current.id)
        client.create_examples(dataset_name=name, examples=[seed])


def append_failure_example(
    *,
    document_text: str,
    school_id: str,
    source_hash: str,
    errors: list[str],
    failure_kind: str,
    source: dict[str, Any] | None = None,
    client: Any = None,
) -> bool:
    """Append one runtime failure row; dedupe by school_id + content hash."""
    if client is None:
        from langsmith import Client

        client = Client()

    if not client.has_dataset(dataset_name=EXTRACTION_DATASET):
        client.create_dataset(dataset_name=EXTRACTION_DATASET)

    fkey = failure_key_for(school_id, source_hash)
    inputs: dict[str, Any] = {
        "failure_key": fkey,
        "school_id": school_id,
        "failure_kind": failure_kind,
        "document_fingerprint": document_fingerprint(document_text),
    }
    if source is not None:
        inputs["source"] = source
    else:
        inputs["document_text"] = document_text

    example = {
        "inputs": inputs,
        "outputs": {
            "notes": " | ".join(errors),
            "source": RUNTIME_SOURCE,
        },
    }

    dataset = client.read_dataset(dataset_name=EXTRACTION_DATASET)
    for ex in client.list_examples(dataset_id=dataset.id):
        if example_key(ex.inputs) == fkey:
            return False

    client.create_examples(dataset_name=EXTRACTION_DATASET, examples=[example])
    return True
