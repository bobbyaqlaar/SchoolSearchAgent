import io

import pandas as pd


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self) -> None:
        return None


def _private_schools_bytes() -> bytes:
    buffer = io.BytesIO()
    main = pd.DataFrame(
        [
            {
                "School Name": "GEMS Modern Academy",
                "Location": "Nad Al Sheba",
                "Curriculum": "Indian",
                "Latest DSIB Rating": "Outstanding",
                "Grades": "KG1-Grade 12",
            }
        ]
    )
    fees = pd.DataFrame(
        [
            {
                "School Name": "GEMS Modern Academy",
                "KG 1": 30000,
                "KG 2": 30000,
                "GRADE 1": 35000,
                "GRADE 12": 60000,
            }
        ]
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        main.to_excel(writer, sheet_name="Main information 2024-2025", index=False, startrow=1)
        fees.to_excel(writer, sheet_name="Fees 2024-2025", index=False, startrow=1)
    return buffer.getvalue()


def test_parse_private_schools_workbook():
    from dubai.data_sources import parse_private_schools_workbook, parse_source_to_school

    sources = parse_private_schools_workbook(_private_schools_bytes())
    assert len(sources) == 1
    assert sources[0]["school_id"] == "gems-modern-academy"
    model = parse_source_to_school(sources[0])
    assert model.neighborhood == "Nad Al Sheba"
    assert len(model.fees) == 4
    grades = {fee.grade for fee in model.fees}
    assert "UNNAMED 0" not in grades
    assert min(fee.tuition_fee for fee in model.fees) >= 1000


def test_extract_fees_ignores_main_enrollment_columns():
    import pandas as pd

    from dubai.data_sources import _extract_fees_from_row

    row = pd.Series(
        {
            "school_name": "Example School",
            "2024_25_enrollments": 3941,
            "2010_11_enrolments": 2254,
            "main_telephone": 97143263339,
            "kg_1": 37368,
        }
    )
    fees = _extract_fees_from_row(row)
    assert len(fees) == 1
    assert fees[0].grade == "KG 1"
    assert fees[0].tuition_fee == 37368


def test_parse_workbook_matches_fees_sheet_with_normalized_school_name():
    import io

    import pandas as pd

    from dubai.data_sources import parse_private_schools_workbook, parse_source_to_school

    buffer = io.BytesIO()
    main = pd.DataFrame(
        [{"School Name": "Delhi Private School L.L.C", "Location": "Garhoud", "Curriculum": "Indian"}]
    )
    fees = pd.DataFrame(
        [{"School Name": "Delhi Private School", "": "مدرسة دلهي الخاصة", "GRADE 1": 18000, "GRADE 2": 19000}]
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        main.to_excel(writer, sheet_name="Main information 2024-2025", index=False, startrow=1)
        fees.to_excel(writer, sheet_name="Fees 2024-2025", index=False, startrow=1)
    model = parse_source_to_school(parse_private_schools_workbook(buffer.getvalue())[0])
    assert len(model.fees) == 2
    assert model.fees[0].tuition_fee == 18000


def test_parse_workbook_uses_latest_fees_sheet():
    import io

    import pandas as pd

    from dubai.data_sources import parse_private_schools_workbook, parse_source_to_school

    buffer = io.BytesIO()
    main = pd.DataFrame([{"School Name": "Test School", "Location": "Mirdif", "Curriculum": "UK"}])
    fees_old = pd.DataFrame([{"School Name": "Test School", "KG 1": 10000}])
    fees_new = pd.DataFrame([{"School Name": "Test School", "KG 1": 20000}])
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        main.to_excel(writer, sheet_name="Main information 2024-2025", index=False, startrow=1)
        fees_old.to_excel(writer, sheet_name="Fees 2023-2024", index=False, startrow=1)
        fees_new.to_excel(writer, sheet_name="Fees 2024-2025", index=False, startrow=1)
    payload = parse_private_schools_workbook(buffer.getvalue())[0]["raw_payload"]
    model = parse_source_to_school(parse_private_schools_workbook(buffer.getvalue())[0])
    assert payload["academic_year"] == "2024-2025"
    assert len(model.fees) == 1
    assert model.fees[0].tuition_fee == 20000


def test_fetch_registry_downloads_private_schools_workbook(mocker, tmp_path):
    mocker.patch(
        "dubai.data_sources.requests.get",
        return_value=_FakeResponse(_private_schools_bytes()),
    )
    from dubai.data_sources import fetch_registry

    sources = fetch_registry(cache_dir=str(tmp_path))
    assert len(sources) == 1
    assert sources[0]["school_name"] == "GEMS Modern Academy"


def test_fetch_registry_uses_cache_when_download_fails(tmp_path, mocker):
    cache = tmp_path / "private_schools.xlsx"
    cache.write_bytes(_private_schools_bytes())
    mocker.patch("dubai.data_sources.requests.get", side_effect=RuntimeError("network down"))
    mocker.patch("dubai.data_sources._download_via_curl", return_value=None)

    from dubai.data_sources import download_private_schools_workbook

    content = download_private_schools_workbook(cache_dir=str(tmp_path))
    assert content is not None
    from dubai.data_sources import parse_private_schools_workbook

    assert len(parse_private_schools_workbook(content)) == 1


def test_download_falls_back_to_curl_when_requests_fails(mocker, tmp_path):
    mocker.patch(
        "dubai.data_sources.requests.get",
        side_effect=RuntimeError("ssl verify failed"),
    )
    mocker.patch(
        "dubai.data_sources._download_via_curl",
        return_value=_private_schools_bytes(),
    )
    from dubai.data_sources import download_private_schools_workbook

    content = download_private_schools_workbook(cache_dir=str(tmp_path))
    assert content is not None
    assert (tmp_path / "private_schools.xlsx").exists()


def test_private_schools_workbook_url():
    from dubai.data_sources import KHDA_OPEN_DATA_PAGE, PRIVATE_SCHOOLS_WORKBOOK_URL

    assert PRIVATE_SCHOOLS_WORKBOOK_URL == (
        "https://web.khda.gov.ae/KHDA/media/KHDA/DubaiPrivateSchoolsOpenData.xlsx"
    )
    assert "web.khda.gov.ae" in KHDA_OPEN_DATA_PAGE


def test_parse_workbook_missing_main_sheet():
    import io

    import pandas as pd

    from dubai.data_sources import parse_private_schools_workbook

    buffer = io.BytesIO()
    fees = pd.DataFrame([{"School Name": "X", "KG 1": 1000}])
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        fees.to_excel(writer, sheet_name="Fees 2024-2025", index=False, startrow=1)
    assert parse_private_schools_workbook(buffer.getvalue()) == []


def test_parse_workbook_main_only_no_fees_sheet():
    import io

    import pandas as pd

    from dubai.data_sources import parse_private_schools_workbook, parse_source_to_school

    buffer = io.BytesIO()
    main = pd.DataFrame(
        [{"School Name": "Horizons English School", "Location": "Mirdif", "Curriculum": "UK, IB"}]
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        main.to_excel(writer, sheet_name="Main information 2024-2025", index=False, startrow=1)
    sources = parse_private_schools_workbook(buffer.getvalue())
    assert len(sources) == 1
    model = parse_source_to_school(sources[0])
    assert model.curriculums == ["UK", "IB"]
    assert model.fees == []


def test_parse_workbook_normalizes_international_baccalaureate_to_ib():
    import io

    import pandas as pd

    from dubai.data_sources import parse_private_schools_workbook, parse_source_to_school

    buffer = io.BytesIO()
    main = pd.DataFrame(
        [
            {
                "School Name": "IB School",
                "Location": "Mirdif",
                "Curriculum": "International Baccalaureate",
            }
        ]
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        main.to_excel(writer, sheet_name="Main information 2024-2025", index=False, startrow=1)
    sources = parse_private_schools_workbook(buffer.getvalue())
    model = parse_source_to_school(sources[0])
    assert model.curriculums == ["IB"]


def test_parse_workbook_skips_blank_school_name():
    import io

    import pandas as pd

    from dubai.data_sources import parse_private_schools_workbook

    buffer = io.BytesIO()
    main = pd.DataFrame(
        [
            {"School Name": "", "Location": "Nowhere"},
            {"School Name": "Valid School", "Location": "Mirdif"},
        ]
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        main.to_excel(writer, sheet_name="Main information 2024-2025", index=False, startrow=1)
    sources = parse_private_schools_workbook(buffer.getvalue())
    assert len(sources) == 1
    assert sources[0]["school_name"] == "Valid School"


def test_fetch_registry_empty_when_download_and_cache_missing(mocker, tmp_path):
    mocker.patch("dubai.data_sources.requests.get", side_effect=RuntimeError("offline"))
    mocker.patch("dubai.data_sources._download_via_curl", return_value=None)
    from dubai.data_sources import fetch_registry

    assert fetch_registry(cache_dir=str(tmp_path)) == []


def test_parse_source_filters_non_dict_fees():
    from dubai.data_sources import parse_source_to_school

    source = {
        "school_id": "test-school",
        "school_name": "Test School",
        "raw_payload": {
            "name": "Test School",
            "neighborhood": "Mirdif",
            "fees": [{"grade": "GRADE 1", "tuition_fee": 1000.0}, "bad", None],
        },
    }
    model = parse_source_to_school(source)
    assert len(model.fees) == 1
    assert model.fees[0].grade == "GRADE 1"

