"""Tests for evals.feedback runtime failure recording."""

from __future__ import annotations

from evals.feedback import LangSmithFailureRecorder, NoOpFailureRecorder, get_failure_recorder


def test_noop_recorder_always_false():
    recorder = NoOpFailureRecorder()
    assert recorder.record(
        document_text="doc",
        school_id="x",
        source_hash="h",
        errors=["e"],
        failure_kind="validation",
    ) is False


def test_get_failure_recorder_returns_langsmith_recorder():
    assert isinstance(get_failure_recorder(), LangSmithFailureRecorder)


def test_langsmith_recorder_skips_without_api_key(mocker):
    mocker.patch(
        "evals.feedback.get_settings",
        return_value=mocker.Mock(langchain_api_key=None),
    )
    append = mocker.patch("evals.datasets.append_failure_example")
    recorder = LangSmithFailureRecorder()
    assert recorder.record(
        document_text="doc",
        school_id="x",
        source_hash="h",
        errors=["e"],
        failure_kind="validation",
    ) is False
    append.assert_not_called()


def test_langsmith_recorder_skips_empty_document(mocker):
    mocker.patch(
        "evals.feedback.get_settings",
        return_value=mocker.Mock(langchain_api_key="ls-key"),
    )
    append = mocker.patch("evals.datasets.append_failure_example")
    recorder = LangSmithFailureRecorder()
    assert recorder.record(
        document_text="   ",
        school_id="x",
        source_hash="h",
        errors=["e"],
        failure_kind="validation",
    ) is False
    append.assert_not_called()


def test_langsmith_recorder_writes_on_success(mocker):
    mocker.patch(
        "evals.feedback.get_settings",
        return_value=mocker.Mock(langchain_api_key="ls-key"),
    )
    append = mocker.patch("evals.datasets.append_failure_example", return_value=True)
    recorder = LangSmithFailureRecorder()
    source = {"school_id": "gems-modern-academy"}
    assert recorder.record(
        document_text='{"name":"GEMS"}',
        school_id="gems-modern-academy",
        source_hash="abc",
        errors=["bad fees"],
        failure_kind="extraction",
        source=source,
    ) is True
    append.assert_called_once_with(
        document_text='{"name":"GEMS"}',
        school_id="gems-modern-academy",
        source_hash="abc",
        errors=["bad fees"],
        failure_kind="extraction",
        source=source,
    )


def test_langsmith_recorder_swallows_append_errors(mocker):
    mocker.patch(
        "evals.feedback.get_settings",
        return_value=mocker.Mock(langchain_api_key="ls-key"),
    )
    mocker.patch("evals.datasets.append_failure_example", side_effect=RuntimeError("api down"))
    recorder = LangSmithFailureRecorder()
    assert recorder.record(
        document_text="doc",
        school_id="x",
        source_hash="h",
        errors=["e"],
        failure_kind="validation",
    ) is False
