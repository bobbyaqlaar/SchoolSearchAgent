"""Data-quality guardrails (README real-time evaluation constraints 1 & 3).

Validates extracted school data before any database commit and provides a
user-friendly negative response so failures never surface as stack traces.
"""

from __future__ import annotations

from dubai.schemas import SchoolDataModel

_NEGATIVE_RESPONSE = (
    "We could not retrieve verified information for this request right now. "
    "Please adjust your search or try again later."
)


def validate_school(data: SchoolDataModel) -> list[str]:
    """Return a list of validation error strings (empty == valid)."""
    errors: list[str] = []

    if not data.school_id or not data.name:
        errors.append("Missing core identity fields (school_id or name)")

    if not data.neighborhood or not data.neighborhood.strip():
        errors.append(f"School '{data.name}' failed geographic neighborhood check")

    if not data.fees:
        errors.append(f"School '{data.name}' has empty or unparsed fee listings")
    else:
        for fee in data.fees:
            if fee.tuition_fee <= 0:
                errors.append(
                    f"Invalid pricing extracted for {fee.grade}: {fee.tuition_fee} AED"
                )

    return errors


def safe_negative_response() -> str:
    """Standard user-facing message emitted on failure."""
    return _NEGATIVE_RESPONSE
