from dubai.schemas import FeeItem, SchoolDataModel


def _school() -> SchoolDataModel:
    return SchoolDataModel(
        school_id="gems-modern-academy",
        name="GEMS Modern Academy",
        neighborhood="Nad Al Sheba",
        curriculums=["Indian"],
        fees=[FeeItem(grade="Grade 1", tuition_fee=30000.0)],
        academic_year="2025-2026",
        khda_rating="Outstanding",
    )


def _source(school: SchoolDataModel | None = None) -> dict:
    model = school or _school()
    return {
        "school_id": model.school_id,
        "school_name": model.name,
        "hash": "abc123",
        "document_text": "open-data-json",
        "raw_payload": {
            "name": model.name,
            "neighborhood": model.neighborhood,
            "curriculums": model.curriculums,
            "fees": [fee.model_dump() for fee in model.fees],
            "academic_year": model.academic_year,
            "khda_rating": model.khda_rating,
        },
    }


class _FakeClient:
    def __init__(self, existing_hashes=None, exists_ids=None):
        self._hashes = existing_hashes or {}
        self._exists = set(exists_ids or [])
        self.upserts = []

    def get_sync_hash(self, school_id):
        return self._hashes.get(school_id)

    def upsert_school(self, data, *, sync_hash):
        self.upserts.append((data, sync_hash))
        return data.school_id not in self._exists

    def clear_school_fees(self, school_id):
        self.upserts.append(("clear_fees", school_id))


def test_discover_sources_node(mocker):
    from dubai import agent as agent_mod

    mocker.patch.object(
        agent_mod, "fetch_registry", return_value=[{"school_id": "x", "hash": "h"}]
    )
    a = agent_mod.DubaiSyncAgent(_FakeClient())
    out = a.discover_sources_node({})
    assert out["discovered_sources"] == [{"school_id": "x", "hash": "h"}]


def test_evaluate_delta_enqueues_changed_only():
    from dubai.agent import DubaiSyncAgent

    client = _FakeClient(existing_hashes={"a": "same", "b": "old"})
    a = DubaiSyncAgent(client)
    state = {
        "discovered_sources": [
            {"school_id": "a", "hash": "same"},
            {"school_id": "b", "hash": "new"},
            {"school_id": "c", "hash": "new"},
        ]
    }
    out = a.evaluate_delta_node(state)
    ids = {s["school_id"] for s in out["pending_syncs"]}
    assert ids == {"b", "c"}
    assert out["audit_logs"]["initial_pending_count"] == 2


def test_extract_node_parses_open_data_source():
    from dubai.agent import DubaiSyncAgent

    a = DubaiSyncAgent(_FakeClient())
    source = _source()
    state = {"pending_syncs": [source], "audit_logs": {}}
    out = a.extract_and_parse_node(state)
    assert len(out["extracted_payloads"]) == 1
    _, parsed, document_text = out["extracted_payloads"][0]
    assert parsed.name == "GEMS Modern Academy"
    assert document_text == "open-data-json"


def test_extract_node_records_parse_failure(mocker):
    from dubai.agent import DubaiSyncAgent

    def _boom(_source):
        raise ValueError("bad row")

    recorder = mocker.Mock()
    recorder.record.return_value = True
    a = DubaiSyncAgent(_FakeClient(), parser=_boom, failure_recorder=recorder)
    source = _source()
    out = a.extract_and_parse_node({"pending_syncs": [source], "audit_logs": {}})
    assert out["extracted_payloads"] == []
    assert out["audit_logs"]["extraction_failures"] == 1
    recorder.record.assert_called_once()


def test_upsert_node_skips_invalid():
    from evals.feedback import NoOpFailureRecorder
    from dubai.agent import DubaiSyncAgent

    invalid = _school()
    invalid.fees = []
    client = _FakeClient()
    a = DubaiSyncAgent(client, failure_recorder=NoOpFailureRecorder())
    source = _source(invalid)
    state = {
        "extracted_payloads": [(source, invalid, source["document_text"])],
        "audit_logs": {"initial_pending_count": 1},
    }
    out = a.upsert_knowledge_graph_node(state)
    assert client.upserts == [("clear_fees", "gems-modern-academy")]
    assert out["audit_logs"]["validation_failures"] == 1


def test_upsert_node_writes_valid():
    from evals.feedback import NoOpFailureRecorder
    from dubai.agent import DubaiSyncAgent

    valid = _school()
    client = _FakeClient()
    a = DubaiSyncAgent(client, failure_recorder=NoOpFailureRecorder())
    source = _source(valid)
    state = {
        "extracted_payloads": [(source, valid, source["document_text"])],
        "audit_logs": {"initial_pending_count": 1},
    }
    out = a.upsert_knowledge_graph_node(state)
    assert len(client.upserts) == 1
    assert out["audit_logs"]["created"] == 1


def test_route_conditional():
    from dubai.agent import route_conditional_sync

    assert route_conditional_sync({"pending_syncs": [1]}) == "extract_data"
    assert route_conditional_sync({"pending_syncs": []}) == "skip_sync"


def test_compile_workflow():
    from dubai.agent import DubaiSyncAgent, compile_sync_workflow

    workflow = compile_sync_workflow(DubaiSyncAgent(_FakeClient()))
    assert workflow is not None
