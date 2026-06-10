"""Smoke-test open-data parsing for a known school (no Neo4j, no LLM)."""

from __future__ import annotations

from dubai.data_sources import fetch_registry, parse_source_to_school
from dubai.guardrails import validate_school

SCHOOL_ID = "gems-modern-academy"


def main() -> int:
    sources = fetch_registry()
    match = next((s for s in sources if s["school_id"] == SCHOOL_ID), None)
    if match is None:
        print(f"School {SCHOOL_ID} not found ({len(sources)} records parsed).")
        return 1

    model = parse_source_to_school(match)
    errors = validate_school(model)
    if errors:
        print("Validation failed:", " | ".join(errors))
        return 1

    print(f"OK: parsed {model.name} with {len(model.fees)} fees from KHDA open data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
