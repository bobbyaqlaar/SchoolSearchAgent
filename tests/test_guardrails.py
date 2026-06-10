from dubai.schemas import FeeItem, SchoolDataModel


def _valid_school() -> SchoolDataModel:
    return SchoolDataModel(
        school_id="gems-modern-academy",
        name="GEMS Modern Academy",
        neighborhood="Nad Al Sheba",
        curriculums=["Indian"],
        fees=[FeeItem(grade="Grade 1", tuition_fee=30000.0)],
        academic_year="2025-2026",
        khda_rating="Outstanding",
    )


def test_valid_school_has_no_errors():
    from dubai.guardrails import validate_school

    assert validate_school(_valid_school()) == []


def test_missing_name_flagged():
    from dubai.guardrails import validate_school

    school = _valid_school()
    school.name = ""
    errors = validate_school(school)
    assert any("name" in e.lower() for e in errors)


def test_empty_fees_flagged():
    from dubai.guardrails import validate_school

    school = _valid_school()
    school.fees = []
    errors = validate_school(school)
    assert any("fee" in e.lower() for e in errors)


def test_negative_fee_flagged():
    from dubai.guardrails import validate_school

    school = _valid_school()
    school.fees = [FeeItem(grade="Grade 1", tuition_fee=-5.0)]
    errors = validate_school(school)
    assert any("Grade 1" in e for e in errors)


def test_missing_neighborhood_flagged():
    from dubai.guardrails import validate_school

    school = _valid_school()
    school.neighborhood = "  "
    errors = validate_school(school)
    assert any("geographic" in e.lower() or "neighborhood" in e.lower() for e in errors)


def test_safe_negative_response_is_friendly():
    from dubai.guardrails import safe_negative_response

    message = safe_negative_response()
    assert "Traceback" not in message
    assert len(message) > 0
