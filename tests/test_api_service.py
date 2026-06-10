import pytest
from fastapi.testclient import TestClient


class _FakeEngine:
    def search_filtered(self, **kwargs):
        return [
            {
                "school_id": "gems-modern-academy",
                "school_name": "GEMS Modern Academy",
                "location": "Nad Al Sheba",
                "latest_rating": "Outstanding",
                "min_fee": 30000.0,
                "max_fee": 63792.0,
                "curriculums": ["Indian"],
            }
        ]

    def search_by_specific_class(self, target_grade, max_budget, curriculum=None):
        return self.search_filtered(
            grade=target_grade, max_budget=max_budget, curriculum=curriculum
        )

    def get_school_detail(self, school_id):
        if school_id == "missing":
            return None
        return {"school_name": "GEMS Modern Academy", "curriculums": ["Indian"]}

    def compare_schools(self, ids):
        return [{"school_name": s, "min_fee": 20000.0} for s in ids]

    def facets(self):
        return {
            "curriculums": ["UK", "IB"],
            "neighborhoods": ["Mirdif"],
            "ratings": ["Outstanding"],
            "grades": ["Year 7", "Grade 1"],
        }

    def close(self):
        return None


@pytest.fixture()
def client():
    import api_service

    api_service.app.dependency_overrides[api_service.get_dashboard_db] = (
        lambda: _FakeEngine()
    )
    yield TestClient(api_service.app)
    api_service.app.dependency_overrides.clear()


def test_health(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "operational"


def test_list_models(client):
    resp = client.get("/api/models")
    assert resp.status_code == 200
    assert "gpt-4o" in resp.json()


def test_search_returns_envelope(client):
    resp = client.get("/api/schools/search", params={"grade": "Grade 1", "max_budget": 40000})
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "telemetry" in body
    assert body["data"][0]["school_name"] == "GEMS Modern Academy"


def test_cors_header_present(client):
    resp = client.get(
        "/api/models", headers={"Origin": "http://localhost:3000"}
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_school_detail(client):
    resp = client.get("/api/schools/gems-modern-academy")
    assert resp.status_code == 200
    assert resp.json()["data"]["school_name"] == "GEMS Modern Academy"


def test_school_detail_missing_404(client):
    resp = client.get("/api/schools/missing")
    assert resp.status_code == 404


def test_compare(client):
    resp = client.get("/api/schools/compare", params=[("ids", "a"), ("ids", "b")])
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


def test_facets(client):
    resp = client.get("/api/facets")
    assert resp.status_code == 200
    assert "UK" in resp.json()["data"]["curriculums"]


def test_ask_model_failure_503(client, mocker):
    mocker.patch("api_service.run_ask", side_effect=RuntimeError("missing API key"))

    resp = client.post("/api/ask", json={"question": "hi", "selected_model": "gpt-4o"})
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"]


def test_ask_unknown_model_422(client):
    resp = client.post("/api/ask", json={"question": "hi", "selected_model": "nope"})
    assert resp.status_code == 422


def test_ask_returns_answer_and_telemetry(client, mocker):
    from dubai.ask_agent import AskResult

    mocker.patch(
        "api_service.run_ask",
        return_value=AskResult(
            answer="GEMS Modern Academy is rated Outstanding.",
            schools=[],
        ),
    )

    resp = client.post(
        "/api/ask", json={"question": "Tell me about GEMS", "selected_model": "gpt-4o"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body["data"]
    assert body["data"]["model"] == "gpt-4o"
    assert "schools" in body["data"]
    assert "telemetry" in body


def test_ask_default_model(client, mocker):
    import api_service
    from dubai.ask_agent import AskResult

    mocker.patch(
        "api_service.run_ask",
        return_value=AskResult(answer="ok", schools=[]),
    )

    resp = client.post("/api/ask", json={"question": "hi"})
    assert resp.status_code == 200
    assert resp.json()["data"]["model"] == api_service.settings.default_model


def test_ask_string_response_fallback(client, mocker):
    from dubai.ask_agent import AskResult

    mocker.patch(
        "api_service.run_ask",
        return_value=AskResult(answer="plain string answer", schools=[]),
    )

    resp = client.post("/api/ask", json={"question": "hi", "selected_model": "gpt-4o"})
    assert resp.status_code == 200
    assert resp.json()["data"]["answer"] == "plain string answer"


class _BrokenEngine(_FakeEngine):
    def search_filtered(self, **kwargs):
        raise RuntimeError("neo4j down")

    def compare_schools(self, ids):
        raise RuntimeError("neo4j down")

    def facets(self):
        raise RuntimeError("neo4j down")

    def get_school_detail(self, school_id):
        raise RuntimeError("neo4j down")


@pytest.fixture()
def broken_client():
    import api_service

    api_service.app.dependency_overrides[api_service.get_dashboard_db] = (
        lambda: _BrokenEngine()
    )
    yield TestClient(api_service.app)
    api_service.app.dependency_overrides.clear()


def test_search_db_failure_500(broken_client):
    resp = broken_client.get(
        "/api/schools/search", params={"grade": "Grade 1", "max_budget": 40000}
    )
    assert resp.status_code == 500
    assert "Database failure" in resp.json()["detail"]


def test_compare_db_failure_500(broken_client):
    resp = broken_client.get("/api/schools/compare", params=[("ids", "a")])
    assert resp.status_code == 500


def test_facets_db_failure_500(broken_client):
    resp = broken_client.get("/api/facets")
    assert resp.status_code == 500


def test_school_detail_db_failure_500(broken_client):
    resp = broken_client.get("/api/schools/gems-modern-academy")
    assert resp.status_code == 500


def test_get_dashboard_db_closes_engine(mocker):
    import api_service

    fake = mocker.Mock()
    mocker.patch.object(api_service, "DubaiDashboardEngine", return_value=fake)
    gen = api_service.get_dashboard_db()
    db = next(gen)
    assert db is fake
    gen.close()
    fake.close.assert_called_once()
