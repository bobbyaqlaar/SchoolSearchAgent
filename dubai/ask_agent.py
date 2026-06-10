"""Graph-backed Ask agent — LLM routes questions to Neo4j tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, ToolMessage

from dashboard_queries import DubaiDashboardEngine
from dubai.ask_tools import ASK_SYSTEM_PROMPT, build_ask_tools
from dubai.ask_prompt import preflight_ask_response
from dubai.cost_tracker import CostTracker
from dubai.curriculum import normalize_curriculum_list
from dubai.llm_router import get_ask_chat_model


@dataclass(frozen=True)
class AskResult:
    answer: str
    schools: list[dict[str, Any]]


def _normalize_school_row(row: dict[str, Any]) -> dict[str, Any]:
    min_fee = row.get("min_fee")
    max_fee = row.get("max_fee")
    precise = row.get("precise_annual_fee")
    if min_fee is None and precise is not None:
        min_fee = precise
    if max_fee is None and precise is not None:
        max_fee = precise
    curriculums = row.get("curriculums")
    if curriculums is None:
        curriculums = []
    else:
        curriculums = normalize_curriculum_list(curriculums)
    return {
        "school_id": row.get("school_id"),
        "school_name": row.get("school_name", ""),
        "location": row.get("location", ""),
        "latest_rating": row.get("latest_rating", ""),
        "min_fee": min_fee,
        "max_fee": max_fee,
        "curriculums": curriculums,
    }


def _extract_schools_from_messages(messages: list[Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    schools: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        content = msg.content
        if not isinstance(content, str) or not content.strip():
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        rows: list[dict[str, Any]]
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict) and payload.get("found") is False:
            continue
        elif isinstance(payload, dict):
            rows = [payload]
        else:
            continue
        for row in rows:
            if not isinstance(row, dict) or not row.get("school_name"):
                continue
            key = str(row.get("school_id") or row["school_name"])
            if key in seen:
                continue
            seen.add(key)
            schools.append(_normalize_school_row(row))
    return schools


def run_ask(
    question: str,
    *,
    model_id: str,
    db: DubaiDashboardEngine,
    cost_tracker: CostTracker,
) -> AskResult:
    """Answer a natural-language question using graph tools + the selected LLM."""
    refusal = preflight_ask_response(question)
    if refusal is not None:
        return AskResult(answer=refusal, schools=[])

    tools = build_ask_tools(db)
    model = get_ask_chat_model(model_id)
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=ASK_SYSTEM_PROMPT,
    )
    result = agent.invoke(
        {"messages": [HumanMessage(content=question)]},
        config={"callbacks": [cost_tracker.as_callback(model_id)]},
    )
    messages = result["messages"]
    last = messages[-1]
    answer = getattr(last, "content", str(last))
    schools = _extract_schools_from_messages(messages)
    return AskResult(answer=answer, schools=schools)
