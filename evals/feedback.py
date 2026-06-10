"""Runtime feedback from sync agent guardrails into LangSmith datasets."""

from __future__ import annotations

import logging
from typing import Any, Literal, Protocol

from dubai.settings import get_settings

logger = logging.getLogger(__name__)

FailureKind = Literal["validation", "extraction"]


class FailureRecorder(Protocol):
    def record(
        self,
        *,
        document_text: str,
        school_id: str,
        source_hash: str,
        errors: list[str],
        failure_kind: FailureKind,
        source: dict[str, Any] | None = None,
    ) -> bool:
        """Return True when a new dataset row was written."""
        ...


class LangSmithFailureRecorder:
    """Writes validation/extraction failures to dubai_extraction_failures."""

    def record(
        self,
        *,
        document_text: str,
        school_id: str,
        source_hash: str,
        errors: list[str],
        failure_kind: FailureKind,
        source: dict[str, Any] | None = None,
    ) -> bool:
        settings = get_settings()
        if not settings.langchain_api_key:
            logger.debug(
                "Skipping failure feedback for %s (LANGCHAIN_API_KEY unset)",
                school_id,
            )
            return False
        if not document_text.strip():
            logger.debug("Skipping failure feedback for %s (empty document_text)", school_id)
            return False

        try:
            from evals.datasets import append_failure_example

            written = append_failure_example(
                document_text=document_text,
                school_id=school_id,
                source_hash=source_hash,
                errors=errors,
                failure_kind=failure_kind,
                source=source,
            )
            if written:
                logger.info(
                    "Recorded %s failure for %s in LangSmith dataset",
                    failure_kind,
                    school_id,
                )
            return written
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "Failed to record %s failure for %s: %s",
                failure_kind,
                school_id,
                error,
            )
            return False


class NoOpFailureRecorder:
    def record(
        self,
        *,
        document_text: str,
        school_id: str,
        source_hash: str,
        errors: list[str],
        failure_kind: FailureKind,
        source: dict[str, Any] | None = None,
    ) -> bool:
        return False


def get_failure_recorder() -> FailureRecorder:
    return LangSmithFailureRecorder()
