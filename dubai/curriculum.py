"""Canonical curriculum labels and alias expansion for search + display."""

from __future__ import annotations

import re

# Canonical label -> lowercase aliases (including the canonical itself).
_CURRICULUM_ALIASES: dict[str, frozenset[str]] = {
    "IB": frozenset({"ib", "international baccalaureate"}),
}

_SPLIT_RE = re.compile(r"\s*-\s*|[,/|;|]+")


def canonical_curriculum(value: str) -> str:
    """Map a single curriculum token to its canonical display/filter label."""
    token = value.strip()
    if not token:
        return token
    lowered = token.lower()
    for canon, aliases in _CURRICULUM_ALIASES.items():
        if lowered == canon.lower() or lowered in aliases:
            return canon
    return token


def split_curriculum_value(raw: str) -> list[str]:
    """Split composite workbook values (e.g. 'UK - International Baccalaureate') into canon tags."""
    parts = [part.strip() for part in _SPLIT_RE.split(raw) if part.strip()]
    if not parts:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        canon = canonical_curriculum(part)
        if canon not in seen:
            seen.add(canon)
            ordered.append(canon)
    return ordered


def normalize_curriculum_list(raw_values: list[str]) -> list[str]:
    """Dedupe and canonicalize curriculum tags for API/UI display."""
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in raw_values:
        for canon in split_curriculum_value(raw):
            if canon not in seen:
                seen.add(canon)
                ordered.append(canon)
    return sorted(ordered, key=str.casefold)


def normalize_curriculum_field(raw: object) -> list[str]:
    """Parse a workbook curriculum cell into canonical tags."""
    if raw is None:
        return []
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return []
    parts = [part.strip() for part in re.split(r"[,;/|]+", text) if part.strip()]
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        for canon in split_curriculum_value(part):
            if canon not in seen:
                seen.add(canon)
                ordered.append(canon)
    return ordered


def matching_raw_curriculum_types(
    all_raw_types: list[str],
    filter_value: str,
) -> list[str]:
    """Raw graph `Curriculum.type` values that match a filter selection."""
    target = canonical_curriculum(filter_value)
    matched: list[str] = []
    for raw in all_raw_types:
        if target in split_curriculum_value(raw):
            matched.append(raw)
    if not matched and filter_value.strip():
        matched.append(filter_value.strip())
    return matched
