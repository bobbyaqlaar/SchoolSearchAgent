"""Ask-agent system prompt and curriculum vs location disambiguation helpers."""

from __future__ import annotations

import re

JURISDICTION_REFUSAL = "Sorry, my jurisdiction is limited to the Dubai Emirate of UAE."

INVALID_FEE_TERM_REFUSAL = (
    "Sorry, I can only search KHDA annual tuition fees and budgets in AED — "
    "not rent or housing charges."
)

# KHDA workbook curriculum labels — NOT foreign countries when used in Dubai school search.
KNOWN_CURRICULA: frozenset[str] = frozenset(
    {
        "UK",
        "US",
        "IB",
        "Indian",
        "Australian",
        "American",
        "French",
        "German",
        "Chinese",
        "Japanese",
        "Pakistani",
        "Philippine",
        "Russian",
        "Iranian",
        "BTEC",
        "Ministry of Education",
    }
)

_CURRICULUM_ALIASES: dict[str, frozenset[str]] = {
    "UK": frozenset({"uk", "british", "british curriculum"}),
    "US": frozenset({"us", "american curriculum", "usa"}),
    "Indian": frozenset({"indian", "india"}),
    "Australian": frozenset({"australian", "australia"}),
    "IB": frozenset({"ib", "international baccalaureate"}),
    "French": frozenset({"french", "france"}),
    "German": frozenset({"german", "germany"}),
}

# Country / region names when used with in|of|from → schools abroad (out of scope).
_FOREIGN_SCHOOL_LOCATIONS: frozenset[str] = frozenset(
    {
        "uk",
        "u.k.",
        "united kingdom",
        "britain",
        "great britain",
        "england",
        "scotland",
        "wales",
        "us",
        "u.s.",
        "usa",
        "u.s.a.",
        "united states",
        "america",
        "india",
        "australia",
        "france",
        "germany",
        "canada",
        "singapore",
        "pakistan",
        "china",
        "japan",
        "philippines",
        "russia",
        "iran",
    }
)

_INVALID_FEE_TERMS_RE = re.compile(r"\b(rent|rental|lease|leasing)\b", re.IGNORECASE)

_VALID_FEE_TERMS_RE = re.compile(
    r"\b(fee|fees|tuition|budget|charge|charges|cost|costs|price|pricing|aed)\b",
    re.IGNORECASE,
)

_DUBAI_CONTEXT_RE = re.compile(
    r"\b(dubai|uae|khda|emirates|private school|schools?\b|fee|fees|budget|rating|"
    r"curriculum|grade|year \d|outstanding|very good|tuition|charge|charges)\b",
    re.IGNORECASE,
)

_JURISDICTION_REFUSAL_RE = re.compile(
    r"jurisdiction is limited|dubai emirate of uae",
    re.IGNORECASE,
)

_INVALID_FEE_TERM_REFUSAL_RE = re.compile(
    r"tuition fees and budgets|not rent or housing",
    re.IGNORECASE,
)

ASK_SYSTEM_PROMPT = f"""
You are the Aqlaar Dubai School Finder assistant. All school facts live in a Neo4j KHDA knowledge graph covering **Dubai private schools only**.

## Tool use (mandatory)
- For ANY question about Dubai schools, budgets, fees, ratings, curricula, or neighborhoods, you MUST call a graph tool first. Never say you lack database access.
- **Default search tool** → `search_schools` (curriculum, budget, rating, neighborhood, grade — all optional; combine any filters the user mentions).
- **Budget direction (critical)**:
  - under / below / at most / capped at / max → `max_budget_aed` only
  - above / over / greater than / more than / at least → `min_budget_aed` only — never use `max_budget_aed`
  - Example: "UK schools with fees greater than 70000" → `search_schools(curriculum="UK", min_budget_aed=70000)`
- Curriculum + budget **without** a rating (e.g. "IB schools under AED 120,000") → `search_schools` with `curriculum` and `max_budget_aed` only. Do NOT invent or require a KHDA rating.
- Schools under budget **and** a specific KHDA rating → `search_schools` or `search_schools_by_budget_and_rating`.
- A named school → `lookup_school_by_name`.
- A specific grade/year level plus budget → `search_schools_by_grade_and_budget` or `search_schools` with `grade`.
- Answer ONLY from tool JSON. Empty list → say no schools matched; suggest widening budget, rating, or filters.
- Format matches as a concise bullet list: school name, Dubai neighborhood, rating, fee range (AED).

## Curriculum vs location (critical)
KHDA schools are **in Dubai/UAE** but teach many **international curricula**. Do NOT treat curriculum names as foreign countries.

**Curriculum labels** (pass to the `curriculum` tool parameter when the user mentions them):
UK, US, IB, Indian, Australian, American, French, German, Chinese, Japanese, Pakistani, Philippine, Russian, Iranian, BTEC, Ministry of Education, and similar KHDA curriculum types.

Examples that are **in jurisdiction** — call a tool, do NOT refuse:
- "UK curriculum schools under AED 80,000"
- "Indian schools with Outstanding rating"
- "US curriculum in Mirdif"
- "Australian curriculum, budget 70k, Very Good rating"

**Location / neighborhood** means Dubai areas only (e.g. Mirdif, Jumeirah, Emirates Hills, Nad Al Sheba, Al Barsha) — use the `neighborhood` tool parameter.

**Never** confuse UK/US/Indian/Australian/French/German with the countries when the user uses **location prepositions**:
- "schools **in** UK", "schools **of** UK", "schools **from** India" → they mean schools **located abroad** → jurisdiction refusal. Do NOT call tools with `curriculum="UK"`.
- "UK **curriculum**", "Indian schools" (no foreign in/of/from), "US curriculum in Mirdif" → Dubai curriculum/neighborhood filters → call tools.

## Fee terminology (critical)
- Valid cost words: fee, fees, tuition, budget, charge, charges, cost, AED.
- **Rent / rental / lease** are NOT KHDA tuition — do NOT search the graph. Reply with:
"{INVALID_FEE_TERM_REFUSAL}"

## Jurisdiction refusal (narrow)
Use this refusal ONLY when the user clearly asks about something **outside UAE private schools** with **no** Dubai/KHDA/school-search context (e.g. "What is the capital of France?", "Best schools in London", "schools in UK"):
"{JURISDICTION_REFUSAL}"

Do NOT use the jurisdiction refusal when curriculum country names (UK, US, Indian, etc.) appear as **curriculum filters** together with Dubai school search criteria (budget, rating, fees, grade, KHDA, UAE, Dubai).
Do NOT use the jurisdiction refusal for rent/rental questions — use the fee-term refusal above instead.
""".strip()


def _question_lower(question: str) -> str:
    return question.strip().lower()


def _foreign_place_pattern(place: str) -> str:
    return r"\s+".join(re.escape(part) for part in place.split())


def _foreign_location_re() -> re.Pattern[str]:
    places = sorted(_FOREIGN_SCHOOL_LOCATIONS, key=len, reverse=True)
    alt = "|".join(_foreign_place_pattern(place) for place in places)
    return re.compile(
        rf"\b(?:schools?\s+(?:in|of|from)\s+(?:the\s+)?(?:{alt})|"
        rf"(?:in|of|from)\s+(?:the\s+)?(?:{alt}))\b",
        re.IGNORECASE,
    )


_FOREIGN_LOCATION_RE = _foreign_location_re()


def mentions_foreign_school_location(question: str) -> bool:
    """True when the user locates schools in a foreign country (in/of/from UK, etc.)."""
    q = _question_lower(question)
    if re.search(r"\b(?:uk|us|indian|american|australian)\s+curriculum\b", q):
        return False
    if re.search(
        r"\bcurriculum\s+(?:uk|us|ib|indian|australian|american|french|german)\b", q
    ):
        return False
    return _FOREIGN_LOCATION_RE.search(q) is not None


def uses_invalid_fee_term(question: str) -> bool:
    """True when the user asks about rent/rental instead of tuition/fees/budget."""
    return bool(_INVALID_FEE_TERMS_RE.search(question))


def mentions_curriculum(question: str) -> bool:
    """True when the question names a known KHDA curriculum label or alias."""
    if mentions_foreign_school_location(question):
        return False
    q = _question_lower(question)
    for canon, aliases in _CURRICULUM_ALIASES.items():
        if canon.lower() in q:
            return True
        if any(re.search(rf"\b{re.escape(alias)}\b", q) for alias in aliases):
            return True
    for label in KNOWN_CURRICULA:
        if re.search(rf"\b{re.escape(label.lower())}\b", q):
            return True
    return False


def has_dubai_school_context(question: str) -> bool:
    """True when the question is clearly about Dubai/KHDA school search."""
    if mentions_foreign_school_location(question):
        return False
    if uses_invalid_fee_term(question):
        return False
    if _DUBAI_CONTEXT_RE.search(question):
        return True
    return mentions_curriculum(question) and bool(
        _VALID_FEE_TERMS_RE.search(question)
        or re.search(r"\b(outstanding|rating|school)\b", _question_lower(question))
    )


def is_jurisdiction_refusal(answer: str) -> bool:
    return bool(_JURISDICTION_REFUSAL_RE.search(answer))


def is_invalid_fee_term_refusal(answer: str) -> bool:
    return bool(_INVALID_FEE_TERM_REFUSAL_RE.search(answer))


def preflight_ask_response(question: str) -> str | None:
    """Deterministic refusal before LLM/tools when the question is out of scope."""
    if uses_invalid_fee_term(question):
        return INVALID_FEE_TERM_REFUSAL
    if mentions_foreign_school_location(question):
        return JURISDICTION_REFUSAL
    if is_off_topic_question(question):
        return JURISDICTION_REFUSAL
    return None


def is_off_topic_question(question: str) -> bool:
    """Questions that should receive the jurisdiction refusal (no Dubai school intent)."""
    if mentions_foreign_school_location(question):
        return True
    if uses_invalid_fee_term(question):
        return False
    if has_dubai_school_context(question):
        return False
    off_topic = (
        "capital of",
        "weather in",
        "schools in london",
        "schools in india",
        "best schools in uk",
        "schools in america",
        "schools in australia",
    )
    q = _question_lower(question)
    return any(phrase in q for phrase in off_topic)
