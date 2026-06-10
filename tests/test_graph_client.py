from dubai.schemas import FeeItem, SchoolDataModel


class _FakeResult:
    def __init__(self, single_value=None):
        self._single = single_value

    def single(self):
        return self._single


class _FakeSession:
    def __init__(self, recorder, exists=False):
        self._recorder = recorder
        self._exists = exists

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query, **params):
        self._recorder.append((query, params))
        if query.strip().startswith("MATCH (s:School") and "RETURN s" in query:
            return _FakeResult({"s": 1} if self._exists else None)
        return _FakeResult(None)


class _FakeDriver:
    def __init__(self, exists=False):
        self.calls = []
        self._exists = exists

    def session(self):
        return _FakeSession(self.calls, self._exists)

    def close(self):
        return None


def _school() -> SchoolDataModel:
    return SchoolDataModel(
        school_id="gems-modern-academy",
        name="GEMS Modern Academy",
        neighborhood="Nad Al Sheba",
        curriculums=["Indian", "IB"],
        fees=[FeeItem(grade="Grade 1", tuition_fee=30000.0)],
        academic_year="2025-2026",
        khda_rating="Outstanding",
    )


def test_apply_constraints_runs_statements():
    from dubai.graph_client import Neo4jClient

    driver = _FakeDriver()
    client = Neo4jClient(driver=driver)
    client.apply_constraints()
    statements = [q for q, _ in driver.calls]
    assert any("CREATE CONSTRAINT unique_school_id" in q for q in statements)
    assert len([q for q in statements if "CREATE CONSTRAINT" in q]) >= 4


def test_upsert_school_creates_when_absent():
    from dubai.graph_client import Neo4jClient

    driver = _FakeDriver(exists=False)
    client = Neo4jClient(driver=driver)
    created = client.upsert_school(_school(), sync_hash="abc123")
    assert created is True
    merge_calls = [p for q, p in driver.calls if "MERGE (s:School" in q]
    assert merge_calls
    assert merge_calls[0]["school_id"] == "gems-modern-academy"
    assert merge_calls[0]["fees"][0]["grade"] == "Grade 1"


def test_upsert_cypher_uses_foreach_not_collapsing_unwind():
    # Regression: UNWIND over an empty list collapses the statement pipeline so
    # later MERGEs silently don't run. FOREACH is a safe no-op on empty lists.
    from dubai.graph_client import _UPSERT_CYPHER

    assert "FOREACH (curr_name IN $curriculums" in _UPSERT_CYPHER
    assert "FOREACH (fee_item IN $fees" in _UPSERT_CYPHER
    assert "UNWIND $curriculums" not in _UPSERT_CYPHER
    assert "UNWIND $fees" not in _UPSERT_CYPHER
    assert "DETACH DELETE f" in _UPSERT_CYPHER
    assert "-[:HAS_FEES]->" in _UPSERT_CYPHER
    assert "-[:RATED]->" in _UPSERT_CYPHER


def test_upsert_school_updates_when_present():
    from dubai.graph_client import Neo4jClient

    driver = _FakeDriver(exists=True)
    client = Neo4jClient(driver=driver)
    created = client.upsert_school(_school(), sync_hash="abc123")
    assert created is False
