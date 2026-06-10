"""Pydantic + TypedDict data contracts shared across the pipeline and API.

These are the wire contracts. The API envelope and frontend types mirror them,
so field names here are stable.
"""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class FeeItem(BaseModel):
    grade: str = Field(
        description="Explicit class or grade name parsed from the fee table, "
        "e.g. 'FS1', 'Year 1', 'Grade 10', 'KG2'"
    )
    tuition_fee: float = Field(
        description="Exact annual numeric tuition fee for this class in AED"
    )


class SchoolDataModel(BaseModel):
    school_id: str = Field(
        description="Unique lowercase hyphenated identifier slug for the school"
    )
    name: str = Field(description="Official name of the school")
    neighborhood: str = Field(
        description="Specific neighborhood community area in Dubai"
    )
    curriculums: list[str] = Field(
        default_factory=list,
        description="Academic curricula offered, e.g. UK, US, IB, Indian",
    )
    fees: list[FeeItem] = Field(
        default_factory=list,
        description="Grade-by-grade list of annual tuition fees",
    )
    academic_year: str = Field(
        default="",
        description="Academic year of the fee table, e.g. '2025-2026'",
    )
    khda_rating: str = Field(
        default="",
        description="Official KHDA rating, e.g. Outstanding, Very Good, Good",
    )


class AgentState(TypedDict, total=False):
    discovered_sources: list[dict[str, Any]]
    pending_syncs: list[dict[str, Any]]
    # (source_meta, structured output, raw document_text fed to the LLM)
    extracted_payloads: list[tuple[dict[str, Any], SchoolDataModel, str]]
    audit_logs: dict[str, Any]
    run_id: str
    force_resync: bool
