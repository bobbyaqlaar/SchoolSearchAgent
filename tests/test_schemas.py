def test_fee_item_valid():
    from dubai.schemas import FeeItem

    fee = FeeItem(grade="Year 7", tuition_fee=16245.0)
    assert fee.grade == "Year 7"
    assert fee.tuition_fee == 16245.0


def test_school_data_model():
    from dubai.schemas import FeeItem, SchoolDataModel

    school = SchoolDataModel(
        school_id="gems-modern-academy",
        name="GEMS Modern Academy",
        neighborhood="Nad Al Sheba",
        curriculums=["Indian", "IB"],
        fees=[FeeItem(grade="Grade 1", tuition_fee=30000.0)],
        academic_year="2025-2026",
        khda_rating="Outstanding",
    )
    assert school.fees[0].tuition_fee == 30000.0
    assert "IB" in school.curriculums


def test_agent_state_has_run_id():
    from dubai.schemas import AgentState

    keys = AgentState.__annotations__
    assert "run_id" in keys
    assert "discovered_sources" in keys
    assert "pending_syncs" in keys
    assert "extracted_payloads" in keys
    assert "audit_logs" in keys
