import json

from dubai.ask_tools import build_ask_tools


class _FakeEngine:
    def search_filtered(self, **kwargs):
        self.last_kwargs = kwargs
        return [
            {
                "school_id": "test-ib",
                "school_name": "Test IB School",
                "location": "Mirdif",
                "latest_rating": "Very good",
                "min_fee": 50000,
                "max_fee": 90000,
                "curriculums": ["IB"],
            }
        ]

    def search_by_budget_and_rating(self, *args, **kwargs):
        return []

    def search_by_specific_class(self, *args, **kwargs):
        return []

    def find_school_by_name(self, name: str):
        return None


def test_search_schools_tool_curriculum_and_budget_only():
    eng = _FakeEngine()
    tools = {t.name: t for t in build_ask_tools(eng)}
    out = tools["search_schools"].invoke(
        {"max_budget_aed": 120000, "curriculum": "IB"},
    )
    payload = json.loads(out)
    assert len(payload) == 1
    assert eng.last_kwargs == {
        "max_budget": 120000,
        "min_budget": None,
        "curriculum": "IB",
        "khda_rating": None,
        "neighborhood": None,
        "grade": None,
    }


def test_search_schools_tool_min_budget_for_greater_than():
    eng = _FakeEngine()
    tools = {t.name: t for t in build_ask_tools(eng)}
    tools["search_schools"].invoke(
        {"min_budget_aed": 70000, "curriculum": "UK"},
    )
    assert eng.last_kwargs == {
        "max_budget": None,
        "min_budget": 70000,
        "curriculum": "UK",
        "khda_rating": None,
        "neighborhood": None,
        "grade": None,
    }


def test_search_schools_tool_optional_rating():
    eng = _FakeEngine()
    tools = {t.name: t for t in build_ask_tools(eng)}
    tools["search_schools"].invoke(
        {
            "max_budget_aed": 90000,
            "curriculum": "UK",
            "khda_rating": "Outstanding",
        },
    )
    assert eng.last_kwargs["khda_rating"] == "Outstanding"
    assert eng.last_kwargs["curriculum"] == "UK"
