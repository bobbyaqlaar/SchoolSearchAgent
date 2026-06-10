from evals.eval_parsing import (
    fee_count_accuracy,
    no_negative_fees,
    regression_pass,
    schema_valid,
)
from evals.eval_qa import semantic_match


def test_regression_pass_true():
    out = {"fees_count": 3, "has_neighborhood": True}
    assert regression_pass(out)["score"] == 1.0


def test_regression_pass_false_no_fees():
    out = {"fees_count": 0, "has_neighborhood": True}
    assert regression_pass(out)["score"] == 0.0


def test_no_negative_fees():
    good = {"fees": [{"tuition_fee": 100.0}, {"tuition_fee": 200.0}]}
    bad = {"fees": [{"tuition_fee": -5.0}]}
    empty = {"fees": []}
    assert no_negative_fees(good)["score"] == 1.0
    assert no_negative_fees(bad)["score"] == 0.0
    assert no_negative_fees(empty)["score"] == 0.0


def test_schema_valid():
    out = {"neighborhood": "Mirdif", "fees": [{"grade": "Year 1", "tuition_fee": 100.0}]}
    assert schema_valid(out)["score"] == 1.0


def test_fee_count_accuracy():
    res = fee_count_accuracy({"fees_count": 2}, {"expected_fee_count": 4})
    assert res["score"] == 0.5
    full = fee_count_accuracy({"fees_count": 4}, {"expected_fee_count": 4})
    assert full["score"] == 1.0


def test_fee_count_accuracy_skips_unlabeled_runtime():
    res = fee_count_accuracy({"fees_count": 0}, {"notes": "missing fees", "source": "runtime"})
    assert res["score"] == 1.0
    assert "skipped" in res.get("comment", "")


def test_target_parsing_runner_parses_source():
    from evals.eval_parsing import target_parsing_runner

    source = {
        "school_id": "gems-modern-academy",
        "school_name": "GEMS Modern Academy",
        "raw_payload": {
            "name": "GEMS Modern Academy",
            "neighborhood": "Nad Al Sheba",
            "curriculums": ["Indian"],
            "fees": [{"grade": "GRADE 1", "tuition_fee": 30000.0}],
            "academic_year": "2024-2025",
            "khda_rating": "Outstanding",
        },
    }
    out = target_parsing_runner({"source": source})
    assert out["fees_count"] == 1
    assert out["has_neighborhood"] is True


def test_regression_pass_false_no_neighborhood():
    out = {"fees_count": 3, "has_neighborhood": False}
    assert regression_pass(out)["score"] == 0.0


def test_schema_valid_rejects_malformed_fees():
    out = {"neighborhood": "Mirdif", "fees": [{"grade": "Year 1"}]}
    assert schema_valid(out)["score"] == 0.0


def test_semantic_match_identical_answers(mocker):
    mocker.patch("evals.eval_qa.cosine_similarity", return_value=1.0)
    res = semantic_match(
        {"answer": "GEMS Modern Academy is Outstanding."},
        {"answer": "GEMS Modern Academy is Outstanding."},
    )
    assert res["score"] >= 0.99


def test_semantic_match_unrelated_answers(mocker):
    mocker.patch("evals.eval_qa.cosine_similarity", return_value=0.1)
    res = semantic_match(
        {"answer": "The weather is sunny today."},
        {"answer": "GEMS Modern Academy is Outstanding."},
    )
    assert res["score"] < 0.5


def test_target_parsing_runner_requires_source():
    from evals.eval_parsing import target_parsing_runner
    import pytest

    with pytest.raises(ValueError, match="registry `source`"):
        target_parsing_runner({})


def test_eval_qa_target_calls_run_ask(mocker):
    from dubai.ask_agent import AskResult
    from evals.eval_qa import target

    mocker.patch(
        "evals.eval_qa.run_ask",
        return_value=AskResult(answer="graph answer", schools=[]),
    )
    mocker.patch("evals.eval_qa.time.sleep")
    out = target({"question": "What is the rating for GEMS?"})
    assert out["answer"] == "graph answer"


def test_semantic_match_missing_answer():
    res = semantic_match({}, {"answer": "x"})
    assert res["score"] == 0.0


class _FakeExample:
    def __init__(self, inputs, outputs=None, _id="e1"):
        self.inputs = inputs
        self.outputs = outputs or {}
        self.id = _id


class _FakeDataset:
    id = "ds-1"


class _FakeClient:
    def __init__(self, existing=None):
        self.has = True
        self.created: list[dict] = []
        self.deleted: list[str] = []
        self._existing = existing or []

    def has_dataset(self, dataset_name):
        return self.has

    def create_dataset(self, dataset_name):
        self.has = True

    def read_dataset(self, dataset_name):
        return _FakeDataset()

    def list_examples(self, dataset_id):
        return self._existing

    def delete_example(self, example_id):
        self.deleted.append(example_id)
        self._existing = [ex for ex in self._existing if ex.id != example_id]

    def create_examples(self, dataset_name, examples):
        for ex in examples:
            self.created.append(ex)
            self._existing.append(
                _FakeExample(ex["inputs"], ex.get("outputs"), f"e{len(self._existing)+1}")
            )


def test_sync_dataset_creates_when_drift():
    from evals.datasets import sync_dataset

    client = _FakeClient(existing=[])
    examples = [{"inputs": {"question": "q1"}, "outputs": {"answer": "a1"}}]
    sync_dataset("dubai_qa", examples, client=client)
    assert len(client.created) == 1


def test_sync_dataset_noop_when_match():
    from evals.datasets import sync_dataset

    client = _FakeClient(existing=[_FakeExample({"question": "q1"}, {"answer": "a1"})])
    examples = [{"inputs": {"question": "q1"}, "outputs": {"answer": "a1"}}]
    sync_dataset("dubai_qa", examples, client=client)
    assert client.created == []
    assert client.deleted == []


def test_ensure_seed_preserves_runtime_rows():
    from evals.datasets import EXTRACTION_SEED, ensure_seed_examples

    runtime = _FakeExample(
        {
            "document_text": "runtime doc",
            "failure_key": "school-a:hash1",
            "school_id": "school-a",
        },
        {"notes": "bad fees", "source": "runtime"},
        "runtime-1",
    )
    client = _FakeClient(existing=[runtime])
    ensure_seed_examples("dubai_extraction_failures", EXTRACTION_SEED, client=client)
    assert any(ex.id == "runtime-1" for ex in client._existing)
    assert len(client.deleted) == 0
    assert len(client.created) == len(EXTRACTION_SEED)


def test_append_failure_dedupes():
    from evals.datasets import append_failure_example

    existing = _FakeExample(
        {"failure_key": "school-a:hash1", "document_text": "doc"},
        {"source": "runtime"},
        "e1",
    )
    client = _FakeClient(existing=[existing])
    written = append_failure_example(
        document_text="doc",
        school_id="school-a",
        source_hash="hash1",
        errors=["empty fees"],
        failure_kind="validation",
        client=client,
    )
    assert written is False
    assert len(client.created) == 0


def test_append_failure_writes_new_row():
    from evals.datasets import append_failure_example

    client = _FakeClient(existing=[])
    written = append_failure_example(
        document_text="doc",
        school_id="school-b",
        source_hash="hash2",
        errors=["empty fees"],
        failure_kind="validation",
        client=client,
    )
    assert written is True
    assert len(client.created) == 1
    assert client.created[0]["outputs"]["source"] == "runtime"


def test_ci_gate_passes():
    import pandas as pd

    from evals.ci_gate import enforce_eval_scores

    class _FakeExperiment:
        def to_pandas(self):
            return pd.DataFrame(
                {
                    "feedback.regression_pass": [1.0, 1.0],
                    "feedback.no_negative_fees": [1.0, 1.0],
                    "feedback.schema_valid": [1.0, 1.0],
                    "feedback.fee_count_accuracy": [1.0, 0.8],
                }
            )

    enforce_eval_scores(_FakeExperiment())


def test_ci_gate_fails_on_regression():
    import pandas as pd
    import pytest

    from evals.ci_gate import enforce_eval_scores

    class _FakeExperiment:
        def to_pandas(self):
            return pd.DataFrame({"feedback.regression_pass": [0.0, 1.0]})

    with pytest.raises(SystemExit) as exc:
        enforce_eval_scores(_FakeExperiment())
    assert exc.value.code == 1
