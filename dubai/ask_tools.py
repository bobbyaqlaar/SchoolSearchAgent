"""LangChain tools for graph-backed Ask / Q&A."""

from __future__ import annotations

import json
from typing import Any

from langchain.tools import tool

from dashboard_queries import DubaiDashboardEngine

from dubai.ask_prompt import ASK_SYSTEM_PROMPT

__all__ = ["ASK_SYSTEM_PROMPT", "build_ask_tools"]


def build_ask_tools(engine: DubaiDashboardEngine) -> list[Any]:
    """Return tool callables bound to a dashboard engine instance."""

    @tool
    def search_schools(
        max_budget_aed: float | None = None,
        min_budget_aed: float | None = None,
        curriculum: str | None = None,
        khda_rating: str | None = None,
        neighborhood: str | None = None,
        grade: str | None = None,
    ) -> str:
        """Search Dubai private schools in the KHDA graph. Use any combination of filters — curriculum and/or budget do NOT require a KHDA rating. max_budget_aed: cap — include schools with at least one annual tuition tier <= this AED amount (under/below/at most). min_budget_aed: floor — include schools whose lowest annual tuition tier is strictly greater than this AED amount (above/over/greater than). Do NOT pass max_budget_aed for "greater than" questions. curriculum: KHDA label such as UK, US, IB, Indian, Australian. khda_rating: optional DSIB rating (Outstanding, Very Good, Good, Acceptable, Weak). neighborhood: Dubai area (e.g. Mirdif). grade: optional grade/year (e.g. Year 7, GRADE 1)."""
        rows = engine.search_filtered(
            max_budget=max_budget_aed,
            min_budget=min_budget_aed,
            curriculum=curriculum,
            khda_rating=khda_rating,
            neighborhood=neighborhood,
            grade=grade,
        )
        return json.dumps(rows, ensure_ascii=False)

    @tool
    def search_schools_by_budget_and_rating(
        max_budget_aed: float,
        khda_rating: str,
        curriculum: str | None = None,
        neighborhood: str | None = None,
    ) -> str:
        """Find Dubai private schools with at least one annual tuition fee <= max_budget_aed (AED) and the given KHDA DSIB rating (e.g. Outstanding, Very Good). Optional curriculum is a KHDA curriculum label (UK, US, IB, Indian, Australian, etc.) — NOT a foreign country. Optional neighborhood is a Dubai area (e.g. Mirdif, Jumeirah)."""
        rows = engine.search_by_budget_and_rating(
            max_budget=max_budget_aed,
            khda_rating=khda_rating,
            curriculum=curriculum,
            neighborhood=neighborhood,
        )
        return json.dumps(rows, ensure_ascii=False)

    @tool
    def search_schools_by_grade_and_budget(
        grade: str,
        max_budget_aed: float,
        curriculum: str | None = None,
    ) -> str:
        """Find schools offering a specific grade (e.g. 'Year 7', 'GRADE 1') with tuition <= max_budget_aed (AED). Optional curriculum is a KHDA label (UK, US, Indian, Australian, IB, etc.)."""
        rows = engine.search_by_specific_class(
            target_grade=grade,
            max_budget=max_budget_aed,
            curriculum=curriculum,
        )
        return json.dumps(rows, ensure_ascii=False)

    @tool
    def lookup_school_by_name(school_name: str) -> str:
        """Look up one Dubai private school by name (partial match)."""
        row = engine.find_school_by_name(school_name)
        if row is None:
            return json.dumps({"found": False, "school_name": school_name})
        return json.dumps(row, ensure_ascii=False)

    return [
        search_schools,
        search_schools_by_budget_and_rating,
        search_schools_by_grade_and_budget,
        lookup_school_by_name,
    ]
