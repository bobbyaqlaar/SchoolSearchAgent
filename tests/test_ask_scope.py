"""Ask scope: prompt helpers, preflight guards, run_ask integration, QA evaluators."""

from __future__ import annotations

from dubai.ask_agent import run_ask
from dubai.ask_prompt import (
    ASK_SYSTEM_PROMPT,
    INVALID_FEE_TERM_REFUSAL,
    JURISDICTION_REFUSAL,
    has_dubai_school_context,
    is_jurisdiction_refusal,
    is_off_topic_question,
    mentions_curriculum,
    mentions_foreign_school_location,
    preflight_ask_response,
    uses_invalid_fee_term,
)
from dubai.cost_tracker import CostTracker
from evals.ask_evaluators import (
    foreign_location_must_refuse,
    invalid_fee_term_refusal_when_required,
    jurisdiction_refusal_when_required,
    no_false_jurisdiction_refusal,
)


class _UnusedEngine:
    def search_filtered(self, **kwargs):  # noqa: ANN003
        raise AssertionError("preflight should block tool use")


# --- System prompt ---


def test_prompt_distinguishes_curriculum_from_location():
    assert "curriculum" in ASK_SYSTEM_PROMPT.lower()
    assert "search_schools" in ASK_SYSTEM_PROMPT
    assert "min_budget_aed" in ASK_SYSTEM_PROMPT
    assert "schools **in** UK" in ASK_SYSTEM_PROMPT
    assert "not rent or housing" in ASK_SYSTEM_PROMPT
    assert "Do NOT invent or require a KHDA rating" in ASK_SYSTEM_PROMPT
    assert "Do NOT use the jurisdiction refusal when curriculum country names" in ASK_SYSTEM_PROMPT


# --- Prompt helpers ---


def test_mentions_foreign_school_location():
    assert mentions_foreign_school_location("Schools of UK with rent less than 70000")
    assert mentions_foreign_school_location("Schools in UK with rent less than 70000")
    assert not mentions_foreign_school_location("UK curriculum schools under 80000")
    assert not mentions_foreign_school_location("US curriculum in Mirdif")


def test_uses_invalid_fee_term():
    assert uses_invalid_fee_term("Schools with rent less than 70000")
    assert not uses_invalid_fee_term("Schools with fees less than 70000")


def test_mentions_curriculum_detects_uk_us_indian():
    assert mentions_curriculum("UK curriculum schools under 80000")
    assert mentions_curriculum("Indian schools with Outstanding rating")
    assert mentions_curriculum("US curriculum in Mirdif")
    assert mentions_curriculum("Australian curriculum budget 70k")


def test_has_dubai_school_context_with_curriculum_and_budget():
    assert has_dubai_school_context("UK curriculum under AED 90000 Outstanding")
    assert has_dubai_school_context("schools in Dubai with IB curriculum")


def test_is_off_topic_capital_of_france():
    assert is_off_topic_question("What is the capital of France?")
    assert not is_off_topic_question("UK curriculum schools under AED 90000 in Dubai")


def test_jurisdiction_refusal_detection():
    assert is_jurisdiction_refusal(JURISDICTION_REFUSAL)
    assert not is_jurisdiction_refusal("Here are UK curriculum schools in Dubai under AED 80,000.")


# --- Preflight ---


def test_foreign_location_in_or_of_uk():
    assert mentions_foreign_school_location("Schools of UK with rent less than 70000")
    assert mentions_foreign_school_location("Schools in UK with rent less than 70000")
    assert preflight_ask_response("Schools in UK with rent less than 70000") == (
        INVALID_FEE_TERM_REFUSAL
    )


def test_foreign_location_fees_still_refuses():
    assert preflight_ask_response("Schools in UK under 70000 AED fees") == (
        JURISDICTION_REFUSAL
    )


def test_uk_curriculum_stays_in_scope():
    assert not mentions_foreign_school_location("UK curriculum schools under AED 90000")
    assert preflight_ask_response("UK curriculum schools under AED 90000") is None


def test_rent_with_valid_curriculum_refuses_fee_term():
    assert uses_invalid_fee_term("UK curriculum schools with rent under 70000")
    assert preflight_ask_response("UK curriculum schools with rent under 70000") == (
        INVALID_FEE_TERM_REFUSAL
    )


def test_us_curriculum_in_mirdif_stays_in_scope():
    assert not mentions_foreign_school_location("US curriculum in Mirdif under 70000")
    assert preflight_ask_response("US curriculum in Mirdif under 70000") is None


# --- run_ask integration ---


def test_run_ask_preflight_blocks_rent_question():
    result = run_ask(
        "Schools of UK with rent less than 70000",
        model_id="github:gpt-4o-mini",
        db=_UnusedEngine(),  # type: ignore[arg-type]
        cost_tracker=CostTracker(),
    )
    assert result.answer == INVALID_FEE_TERM_REFUSAL
    assert result.schools == []


def test_run_ask_preflight_blocks_foreign_location():
    result = run_ask(
        "Schools in UK under 70000 AED fees",
        model_id="github:gpt-4o-mini",
        db=_UnusedEngine(),  # type: ignore[arg-type]
        cost_tracker=CostTracker(),
    )
    assert result.answer == JURISDICTION_REFUSAL
    assert result.schools == []


# --- QA evaluators ---


def test_no_false_jurisdiction_refusal_fails_on_uk_curriculum_search():
    result = no_false_jurisdiction_refusal(
        {"answer": JURISDICTION_REFUSAL},
        {},
        {"question": "UK curriculum Outstanding schools under AED 90000"},
    )
    assert result["score"] == 0.0
    assert "False jurisdiction refusal" in result["comment"]


def test_no_false_jurisdiction_refusal_passes_valid_answer():
    result = no_false_jurisdiction_refusal(
        {"answer": "GEMS Modern Academy offers Indian curriculum with Outstanding rating."},
        {},
        {"question": "Indian curriculum schools with Outstanding rating"},
    )
    assert result["score"] == 1.0


def test_no_false_jurisdiction_refusal_allows_off_topic_skip():
    result = no_false_jurisdiction_refusal(
        {"answer": JURISDICTION_REFUSAL},
        {},
        {"question": "What is the capital of France?"},
    )
    assert result["score"] == 1.0


def test_jurisdiction_refusal_required_for_off_topic():
    result = jurisdiction_refusal_when_required(
        {"answer": "Paris is the capital of France."},
        {},
        {"question": "What is the capital of France?"},
    )
    assert result["score"] == 0.0


def test_jurisdiction_refusal_not_required_for_us_curriculum_search():
    result = jurisdiction_refusal_when_required(
        {"answer": "Several US curriculum schools in Dubai match your budget."},
        {},
        {"question": "US curriculum schools under 70000 AED"},
    )
    assert result["score"] == 1.0


def test_no_false_jurisdiction_refusal_catches_australian_curriculum():
    result = no_false_jurisdiction_refusal(
        {"answer": JURISDICTION_REFUSAL},
        {},
        {"question": "Australian curriculum schools with Very Good rating under 65000"},
    )
    assert result["score"] == 0.0


def test_no_false_jurisdiction_refusal_catches_indian_budget_search():
    result = no_false_jurisdiction_refusal(
        {"answer": JURISDICTION_REFUSAL},
        {},
        {"question": "Show Indian schools below AED 50000"},
    )
    assert result["score"] == 0.0


def test_foreign_location_must_refuse_schools_in_uk():
    result = foreign_location_must_refuse(
        {"answer": "Here are UK curriculum schools in Dubai under 70000."},
        {},
        {"question": "Schools in UK under 70000 AED fees"},
    )
    assert result["score"] == 0.0


def test_foreign_location_passes_on_jurisdiction_refusal():
    result = foreign_location_must_refuse(
        {"answer": JURISDICTION_REFUSAL},
        {},
        {"question": "Schools of UK with fees under 70000"},
    )
    assert result["score"] == 1.0


def test_invalid_fee_term_refusal_for_rent():
    result = invalid_fee_term_refusal_when_required(
        {"answer": "Here are UK schools with fees under 70000."},
        {},
        {"question": "Schools of UK with rent less than 70000"},
    )
    assert result["score"] == 0.0


def test_invalid_fee_term_refusal_passes_on_correct_message():
    result = invalid_fee_term_refusal_when_required(
        {"answer": INVALID_FEE_TERM_REFUSAL},
        {},
        {"question": "Schools in UK with rent less than 70000"},
    )
    assert result["score"] == 1.0
