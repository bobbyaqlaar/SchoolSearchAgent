"""Deterministic evaluators for Ask / Q&A (curriculum vs jurisdiction edge cases)."""

from __future__ import annotations

from typing import Any

from dubai.ask_prompt import (
    has_dubai_school_context,
    is_invalid_fee_term_refusal,
    is_jurisdiction_refusal,
    is_off_topic_question,
    mentions_curriculum,
    mentions_foreign_school_location,
    uses_invalid_fee_term,
)


def no_false_jurisdiction_refusal(
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Fail when a Dubai/curriculum school search is wrongly refused as out-of-jurisdiction."""
    _ = reference_outputs
    answer = str(outputs.get("answer", ""))
    question = str(inputs.get("question", ""))

    if not answer.strip():
        return {
            "key": "no_false_jurisdiction_refusal",
            "score": 0.0,
            "comment": "No answer produced.",
        }

    if is_off_topic_question(question):
        return {
            "key": "no_false_jurisdiction_refusal",
            "score": 1.0,
            "comment": "Off-topic question; jurisdiction refusal allowed.",
        }

    if uses_invalid_fee_term(question):
        return {
            "key": "no_false_jurisdiction_refusal",
            "score": 1.0,
            "comment": "Invalid fee-term question; handled separately.",
        }

    if has_dubai_school_context(question) and is_jurisdiction_refusal(answer):
        hint = "curriculum" if mentions_curriculum(question) else "Dubai school"
        return {
            "key": "no_false_jurisdiction_refusal",
            "score": 0.0,
            "comment": (
                f"False jurisdiction refusal for {hint} search. "
                "UK/US/Indian/Australian etc. are curriculum filters in Dubai, not foreign locations."
            ),
        }

    return {
        "key": "no_false_jurisdiction_refusal",
        "score": 1.0,
        "comment": "No false jurisdiction refusal.",
    }


def jurisdiction_refusal_when_required(
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Fail when a clearly off-topic question should be refused but was answered."""
    _ = reference_outputs
    answer = str(outputs.get("answer", ""))
    question = str(inputs.get("question", ""))

    if not is_off_topic_question(question):
        return {
            "key": "jurisdiction_refusal_when_required",
            "score": 1.0,
            "comment": "In-scope question; refusal not required.",
        }

    if is_jurisdiction_refusal(answer):
        return {
            "key": "jurisdiction_refusal_when_required",
            "score": 1.0,
            "comment": "Correct jurisdiction refusal.",
        }

    return {
        "key": "jurisdiction_refusal_when_required",
        "score": 0.0,
        "comment": "Off-topic question should receive jurisdiction refusal.",
    }


def invalid_fee_term_refusal_when_required(
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Fail when rent/rental is used instead of tuition/fees/budget but was answered with search results."""
    _ = reference_outputs
    answer = str(outputs.get("answer", ""))
    question = str(inputs.get("question", ""))

    if not uses_invalid_fee_term(question):
        return {
            "key": "invalid_fee_term_refusal_when_required",
            "score": 1.0,
            "comment": "Valid fee terminology; refusal not required.",
        }

    if is_invalid_fee_term_refusal(answer):
        return {
            "key": "invalid_fee_term_refusal_when_required",
            "score": 1.0,
            "comment": "Correct fee-term refusal.",
        }

    return {
        "key": "invalid_fee_term_refusal_when_required",
        "score": 0.0,
        "comment": "Rent/rental questions must not run a tuition search — refuse with fee-term message.",
    }


def foreign_location_must_refuse(
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Fail when schools in/of/from a foreign country are treated as Dubai curriculum search."""
    _ = reference_outputs
    answer = str(outputs.get("answer", ""))
    question = str(inputs.get("question", ""))

    if not mentions_foreign_school_location(question):
        return {
            "key": "foreign_location_must_refuse",
            "score": 1.0,
            "comment": "Not a foreign-location question.",
        }

    if uses_invalid_fee_term(question):
        return {
            "key": "foreign_location_must_refuse",
            "score": 1.0,
            "comment": "Handled by fee-term refusal evaluator.",
        }

    if is_jurisdiction_refusal(answer):
        return {
            "key": "foreign_location_must_refuse",
            "score": 1.0,
            "comment": "Correct jurisdiction refusal for foreign location.",
        }

    return {
        "key": "foreign_location_must_refuse",
        "score": 0.0,
        "comment": (
            "Questions like 'schools in/of UK' are out of jurisdiction — "
            "must not return Dubai UK-curriculum search results."
        ),
    }
