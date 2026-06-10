"""KHDA open-data acquisition (private schools Excel only).

Compliant source: official Dubai Private Schools workbook (direct download).

Workbook URL:
  https://web.khda.gov.ae/KHDA/media/KHDA/DubaiPrivateSchoolsOpenData.xlsx

Statistics landing page (reference only):
  https://web.khda.gov.ae/en/Resources/KHDA-data-statistics

No third-party feeds, fact-sheet HTML, PDF scraping, or other KHDA workbooks.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import subprocess
from typing import Any

import pandas as pd
import requests
import certifi

from dubai.schemas import FeeItem, SchoolDataModel
from dubai.curriculum import normalize_curriculum_field

logger = logging.getLogger(__name__)

KHDA_BASE_URL = "https://web.khda.gov.ae"
KHDA_OPEN_DATA_PAGE = f"{KHDA_BASE_URL}/en/Resources/KHDA-data-statistics"
PRIVATE_SCHOOLS_WORKBOOK_URL = (
    "https://web.khda.gov.ae/KHDA/media/KHDA/DubaiPrivateSchoolsOpenData.xlsx"
)

_DEFAULT_CACHE_DIR = "dubai_open_data_cache"
_CACHE_FILENAME = "private_schools.xlsx"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": KHDA_OPEN_DATA_PAGE,
}

_FEE_SHEET_RE = re.compile(r"^Fees\s+(\d{4})-(\d{4})$", re.IGNORECASE)
_MAIN_SHEET_RE = re.compile(r"^Main information\s+(\d{4})-(\d{4})$", re.IGNORECASE)
_GRADE_FEE_COLUMN_RE = re.compile(
    r"^(pre_primary|kg_\d+|grade_\d+|fs_\d+|year_\d+)$",
    re.IGNORECASE,
)
_FEE_ROW_SKIP = frozenset({"school_name", "اسم_المدرسة", "unnamed_0", "unnamed:_0", ""})


def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return cleaned.strip("-")


def _normalize_column(label: object) -> str:
    text = str(label).split("\n")[0].strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame.columns = [_normalize_column(col) for col in frame.columns]
    return frame


def _row_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode("utf-8")).hexdigest()


def _coerce_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() == "nan":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _split_curriculums(raw: object) -> list[str]:
    return normalize_curriculum_field(raw)


def _school_lookup_key(name: str) -> str:
    """Normalize school names for cross-sheet matching (Main vs Fees)."""
    text = name.strip().lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\bl\.?\s*l\.?\s*c\.?\b", " ", text)
    text = re.sub(r"\bllc\b", " ", text)
    text = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_grade_fee_column(column: str) -> bool:
    return bool(_GRADE_FEE_COLUMN_RE.match(column.strip()))


def _grade_label_from_column(column: str) -> str:
    normalized = column.strip().lower()
    if normalized == "pre_primary":
        return "PRE PRIMARY"
    if normalized.startswith("kg_"):
        return f"KG {normalized.split('_', 1)[1]}"
    if normalized.startswith("grade_"):
        return f"GRADE {normalized.split('_', 1)[1]}"
    if normalized.startswith("fs_"):
        return f"FS {normalized.split('_', 1)[1]}"
    if normalized.startswith("year_"):
        return f"YEAR {normalized.split('_', 1)[1]}"
    return column.replace("_", " ").upper()


def _build_fees_by_name(fees_df: pd.DataFrame) -> dict[str, pd.Series]:
    """Index latest Fees-sheet rows by English, Arabic, and normalized keys."""
    fees_by_name: dict[str, pd.Series] = {}
    for _, row in fees_df.iterrows():
        keys: set[str] = set()
        english = str(row.get("school_name", "")).strip()
        arabic = str(row.get("", "")).strip()
        for candidate in (english, arabic):
            if not candidate or candidate.lower() == "nan":
                continue
            keys.add(candidate.casefold())
            keys.add(_school_lookup_key(candidate))
        for key in keys:
            if key:
                fees_by_name[key] = row
    return fees_by_name


def _lookup_fee_row(fees_by_name: dict[str, pd.Series], school_name: str) -> pd.Series | None:
    for key in (school_name.casefold(), _school_lookup_key(school_name)):
        row = fees_by_name.get(key)
        if row is not None:
            return row
    return None


def _latest_sheet(sheet_names: list[str], pattern: re.Pattern[str]) -> str | None:
    matches: list[tuple[int, str]] = []
    for name in sheet_names:
        match = pattern.match(name.strip())
        if match:
            matches.append((int(match.group(1)), name))
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]


def _extract_fees_from_row(row: pd.Series) -> list[FeeItem]:
    """Extract grade-level tuition from a Fees-sheet row (never Main information)."""
    fees: list[FeeItem] = []
    for column, value in row.items():
        col = str(column)
        if col in _FEE_ROW_SKIP or col.endswith("_in_arabic") or not _is_grade_fee_column(col):
            continue
        amount = _coerce_float(value)
        if amount is None or amount <= 0:
            continue
        fees.append(FeeItem(grade=_grade_label_from_column(col), tuition_fee=amount))
    return fees


def _academic_year_from_sheet(sheet_name: str, pattern: re.Pattern[str]) -> str:
    match = pattern.match(sheet_name.strip())
    if not match:
        return ""
    return f"{match.group(1)}-{match.group(2)}"


def _source_record(*, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    document_text = json.dumps({"name": name, **payload}, sort_keys=True, default=str)
    return {
        "school_id": _slugify(name),
        "school_name": name,
        "hash": _row_hash(payload),
        "raw_payload": payload,
        "document_text": document_text,
    }


def parse_private_schools_workbook(content: bytes) -> list[dict[str, Any]]:
    """Parse Dubai Private Schools open-data workbook."""
    workbook = pd.ExcelFile(io.BytesIO(content))
    main_sheet = _latest_sheet(workbook.sheet_names, _MAIN_SHEET_RE)
    fees_sheet = _latest_sheet(workbook.sheet_names, _FEE_SHEET_RE)
    if main_sheet is None:
        logger.warning("Private schools workbook missing main information sheet")
        return []

    main_df = _normalize_frame(pd.read_excel(workbook, sheet_name=main_sheet, header=1))
    fees_df: pd.DataFrame | None = None
    if fees_sheet is not None:
        fees_df = _normalize_frame(pd.read_excel(workbook, sheet_name=fees_sheet, header=1))

    academic_year = _academic_year_from_sheet(main_sheet, _MAIN_SHEET_RE)
    fees_by_name: dict[str, pd.Series] = {}
    if fees_df is not None and "school_name" in fees_df.columns:
        fees_by_name = _build_fees_by_name(fees_df)
        if fees_sheet is not None:
            academic_year = _academic_year_from_sheet(fees_sheet, _FEE_SHEET_RE) or academic_year

    sources: list[dict[str, Any]] = []
    for _, row in main_df.iterrows():
        name = str(row.get("school_name", "")).strip()
        if not name or name.lower() == "nan":
            continue
        location = str(row.get("location", "")).strip()
        if location.lower() == "nan":
            location = ""
        rating = str(row.get("latest_dsib_rating", "")).strip()
        if rating.lower() == "nan":
            rating = ""
        fee_row = _lookup_fee_row(fees_by_name, name)
        fees = _extract_fees_from_row(fee_row) if fee_row is not None else []
        payload = {
            "academic_year": academic_year,
            "name": name,
            "neighborhood": location,
            "curriculums": _split_curriculums(row.get("curriculum")),
            "khda_rating": rating,
            "grades": str(row.get("grades", "")).strip(),
            "fees": [fee.model_dump() for fee in fees],
            "latitude": _coerce_float(row.get("latitude")),
            "longitude": _coerce_float(row.get("longitude")),
        }
        sources.append(_source_record(name=name, payload=payload))
    return sources


def _download_via_curl(url: str, *, timeout: int) -> bytes | None:
    """Fallback when Python SSL store cannot verify KHDA (common on macOS)."""
    try:
        completed = subprocess.run(
            ["curl", "-fsSL", "--max-time", str(timeout), url],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0 or not completed.stdout:
        return None
    return completed.stdout


def download_private_schools_workbook(
    *,
    url: str = PRIVATE_SCHOOLS_WORKBOOK_URL,
    cache_dir: str = _DEFAULT_CACHE_DIR,
    timeout: int = 60,
) -> bytes | None:
    """Download the private schools workbook with local cache fallback."""
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, _CACHE_FILENAME)

    for attempt in range(3):
        try:
            logger.info("Downloading KHDA private schools workbook (attempt %d/3)", attempt + 1)
            response = requests.get(
                url,
                headers=_DEFAULT_HEADERS,
                timeout=timeout,
                verify=certifi.where(),
            )
            response.raise_for_status()
            content = response.content
            with open(cache_path, "wb") as handle:
                handle.write(content)
            return content
        except Exception as error:  # noqa: BLE001
            logger.warning("Download attempt %d failed: %s", attempt + 1, error)

    logger.info("Trying curl fallback for KHDA workbook download")
    curl_content = _download_via_curl(url, timeout=timeout)
    if curl_content:
        with open(cache_path, "wb") as handle:
            handle.write(curl_content)
        return curl_content

    if os.path.exists(cache_path):
        logger.warning("Using cached private schools workbook: %s", cache_path)
        with open(cache_path, "rb") as handle:
            return handle.read()

    logger.error("No live or cached private schools workbook available")
    return None


def fetch_registry(*, cache_dir: str = _DEFAULT_CACHE_DIR) -> list[dict[str, Any]]:
    """Download and parse the KHDA Dubai Private Schools open-data workbook."""
    content = download_private_schools_workbook(cache_dir=cache_dir)
    if content is None:
        return []
    sources = parse_private_schools_workbook(content)
    logger.info("Parsed %d private school records", len(sources))
    return sources


def parse_source_to_school(source: dict[str, Any]) -> SchoolDataModel:
    """Map one registry source (Excel row payload) to SchoolDataModel."""
    payload = source.get("raw_payload", {})
    fees_raw = payload.get("fees", [])
    fees = [FeeItem(**item) for item in fees_raw if isinstance(item, dict)]
    name = str(payload.get("name") or source.get("school_name", "")).strip()
    neighborhood = str(payload.get("neighborhood", "")).strip()
    return SchoolDataModel(
        school_id=source.get("school_id") or _slugify(name),
        name=name,
        neighborhood=neighborhood,
        curriculums=list(payload.get("curriculums") or []),
        fees=fees,
        academic_year=str(payload.get("academic_year", "")),
        khda_rating=str(payload.get("khda_rating", "")),
    )
