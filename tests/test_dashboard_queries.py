class _FakeRecord(dict):
    def data(self):
        return dict(self)


class _FakeResult:
    def __init__(self, rows):
        self._rows = [_FakeRecord(r) for r in rows]

    def __iter__(self):
        return iter(self._rows)

    def single(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, rows_by_substr, recorder):
        self._rows_by_substr = rows_by_substr
        self._recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query, **params):
        self._recorder.append((query, params))
        for substr, rows in self._rows_by_substr.items():
            if substr in query:
                return _FakeResult(rows)
        return _FakeResult([])


class _FakeDriver:
    def __init__(self, rows_by_substr):
        self.calls = []
        self._rows = rows_by_substr

    def session(self):
        return _FakeSession(self._rows, self.calls)

    def close(self):
        return None


def _engine(rows_by_substr):
    from dashboard_queries import DubaiDashboardEngine

    eng = DubaiDashboardEngine.__new__(DubaiDashboardEngine)
    eng.driver = _FakeDriver(rows_by_substr)
    return eng


def test_search_by_budget_and_rating():
    eng = _engine(
        {
            "RETURN DISTINCT": [
                {
                    "school_id": "gems-modern-academy",
                    "school_name": "GEMS Modern Academy",
                    "location": "Nad Al Sheba",
                    "latest_rating": "Outstanding",
                    "min_fee": 30000.0,
                    "max_fee": 60000.0,
                    "curriculums": ["Indian"],
                }
            ]
        }
    )
    rows = eng.search_by_budget_and_rating(90000, "Outstanding")
    assert len(rows) == 1
    assert rows[0]["latest_rating"] == "Outstanding"


def test_search_filtered():
    eng = _engine(
        {
            "RETURN DISTINCT": [
                {
                    "school_id": "gems-modern-academy",
                    "school_name": "GEMS Modern Academy",
                    "location": "Nad Al Sheba",
                    "latest_rating": "Outstanding",
                    "min_fee": 30000.0,
                    "max_fee": 60000.0,
                    "curriculums": ["Indian", "IB"],
                }
            ]
        }
    )
    rows = eng.search_filtered(max_budget=90000, khda_rating="Outstanding")
    assert rows[0]["curriculums"] == ["IB", "Indian"]


def test_search_filtered_min_budget_passed_to_query():
    eng = _engine({"RETURN DISTINCT": []})
    eng.search_filtered(min_budget=70000, curriculum="UK")
    assert len(eng.driver.calls) == 2  # curriculum types lookup + search
    _, params = eng.driver.calls[-1]
    assert params["min_budget"] == 70000.0
    assert params["max_budget"] is None
    assert "min_fee > $min_budget" in eng.driver.calls[-1][0]


def test_find_school_by_name():
    eng = _engine(
        {
            "RETURN": [
                {
                    "school_id": "gems-modern-academy",
                    "school_name": "GEMS Modern Academy",
                    "location": "Nad Al Sheba",
                    "curriculums": ["Indian"],
                    "latest_rating": "Outstanding",
                    "rating_year": "2024-2025",
                    "min_fee": 20000.0,
                    "max_fee": 45000.0,
                }
            ]
        }
    )
    row = eng.find_school_by_name("GEMS Modern")
    assert row["school_name"] == "GEMS Modern Academy"
    assert row["latest_rating"] == "Outstanding"


def test_get_school_detail():
    eng = _engine(
        {
            "RETURN": [
                {
                    "school_name": "GEMS Modern Academy",
                    "location": "Nad Al Sheba",
                    "curriculums": ["Indian", "IB"],
                    "ratings": [{"academic_year": "2025-2026", "rating": "Outstanding"}],
                    "fees": [{"grade": "Grade 1", "tuition_fee": 30000.0}],
                }
            ]
        }
    )
    detail = eng.get_school_detail("gems-modern-academy")
    assert detail["school_name"] == "GEMS Modern Academy"
    assert "Indian" in detail["curriculums"]


def test_get_school_detail_missing_returns_none():
    eng = _engine({})
    assert eng.get_school_detail("nope") is None


def test_compare_schools():
    eng = _engine(
        {
            "RETURN": [
                {"school_name": "A", "location": "X", "latest_rating": "Good", "min_fee": 20000.0},
                {"school_name": "B", "location": "Y", "latest_rating": "Very Good", "min_fee": 25000.0},
            ]
        }
    )
    rows = eng.compare_schools(["a", "b"])
    assert len(rows) == 2
    assert rows[0]["school_name"] == "A"


def test_facets():
    eng = _engine(
        {
            "curriculums": [{"v": "UK"}, {"v": "IB"}],
            "neighborhoods": [{"v": "Mirdif"}],
            "ratings": [{"v": "Outstanding"}],
            "grades": [{"v": "Year 7"}],
        }
    )
    facets = eng.facets()
    assert "UK" in facets["curriculums"]
    assert "Mirdif" in facets["neighborhoods"]
    assert "Outstanding" in facets["ratings"]
    assert "Year 7" in facets["grades"]
