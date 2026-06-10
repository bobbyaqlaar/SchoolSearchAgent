"""LangGraph incremental sync agent.

Four nodes: discover -> evaluate delta -> parse open-data Excel -> upsert.
Structured fields come from the KHDA Dubai Private Schools open-data workbook
only (deterministic Excel parse — no LLM, no fact-sheet or PDF scraping).

Validation failures append to the LangSmith regression dataset when
LANGCHAIN_API_KEY is configured (see evals.feedback).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from evals.feedback import FailureRecorder, get_failure_recorder
from dubai.data_sources import fetch_registry, parse_source_to_school
from dubai.graph_client import Neo4jClient
from dubai.guardrails import validate_school
from dubai.schemas import AgentState, SchoolDataModel
logger = logging.getLogger(__name__)


class DubaiSyncAgent:
    def __init__(
        self,
        client: Neo4jClient,
        *,
        failure_recorder: FailureRecorder | None = None,
        parser: Any = None,
    ) -> None:
        self.db = client
        self._failure_recorder = failure_recorder or get_failure_recorder()
        self._parser = parser or parse_source_to_school

    def _record_failure(
        self,
        *,
        document_text: str,
        school_id: str,
        source_hash: str,
        errors: list[str],
        failure_kind: Literal["validation", "extraction"],
        source: dict[str, Any] | None = None,
    ) -> bool:
        return self._failure_recorder.record(
            document_text=document_text,
            school_id=school_id,
            source_hash=source_hash,
            errors=errors,
            failure_kind=failure_kind,
            source=source,
        )

    def discover_sources_node(self, state: AgentState) -> dict[str, Any]:
        logger.info("[1/4] Loading KHDA private schools open-data workbook...")
        return {"discovered_sources": fetch_registry()}

    def evaluate_delta_node(self, state: AgentState) -> dict[str, Any]:
        logger.info("[2/4] Evaluating delta against graph state...")
        force = bool(state.get("force_resync"))
        if force:
            logger.info("Force resync enabled — all discovered sources queued")
        pending: list[dict[str, Any]] = []
        for source in state.get("discovered_sources", []):
            if force:
                pending.append(source)
                continue
            existing = self.db.get_sync_hash(source["school_id"])
            if existing != source["hash"]:
                pending.append(source)
        return {
            "pending_syncs": pending,
            "audit_logs": {
                "initial_pending_count": len(pending),
                "created": 0,
                "updated": 0,
                "validation_failures": 0,
                "extraction_failures": 0,
                "failures_recorded": 0,
            },
        }

    def extract_and_parse_node(self, state: AgentState) -> dict[str, Any]:
        pending = state.get("pending_syncs", [])
        logger.info("[3/4] Parsing %d open-data records...", len(pending))
        payloads: list[tuple[dict[str, Any], SchoolDataModel, str]] = []
        extraction_failures = 0
        failures_recorded = 0

        for item in pending:
            document_text = str(item.get("document_text", ""))
            try:
                structured = self._parser(item)
                payloads.append((item, structured, document_text))
            except Exception as error:  # noqa: BLE001
                extraction_failures += 1
                logger.warning("Parse failed for %s: %s", item["school_id"], error)
                if self._record_failure(
                    document_text=document_text,
                    school_id=item["school_id"],
                    source_hash=item["hash"],
                    errors=[str(error)],
                    failure_kind="extraction",
                    source=item,
                ):
                    failures_recorded += 1

        audit = dict(state.get("audit_logs", {}))
        audit["extraction_failures"] = extraction_failures
        audit["failures_recorded"] = audit.get("failures_recorded", 0) + failures_recorded
        return {"extracted_payloads": payloads, "audit_logs": audit}

    def upsert_knowledge_graph_node(self, state: AgentState) -> dict[str, Any]:
        logger.info("[4/4] Writing to knowledge graph...")
        created = 0
        updated = 0
        validation_failures = 0
        failures_recorded = 0

        for source_meta, data, document_text in state.get("extracted_payloads", []):
            errors = validate_school(data)
            if errors:
                validation_failures += 1
                logger.warning(
                    "Validation failed for %s: %s",
                    data.school_id,
                    " | ".join(errors),
                )
                if self._record_failure(
                    document_text=document_text,
                    school_id=source_meta["school_id"],
                    source_hash=source_meta["hash"],
                    errors=errors,
                    failure_kind="validation",
                    source=source_meta,
                ):
                    failures_recorded += 1
                self.db.clear_school_fees(data.school_id)
                continue
            was_created = self.db.upsert_school(data, sync_hash=source_meta["hash"])
            if was_created:
                created += 1
            else:
                updated += 1

        audit = dict(state.get("audit_logs", {}))
        audit["created"] = created
        audit["updated"] = updated
        audit["validation_failures"] = validation_failures
        audit["failures_recorded"] = audit.get("failures_recorded", 0) + failures_recorded
        return {"audit_logs": audit}


def route_conditional_sync(state: AgentState) -> Literal["extract_data", "skip_sync"]:
    if state.get("pending_syncs"):
        return "extract_data"
    logger.info("Graph up to date. Skipping extraction.")
    return "skip_sync"


def compile_sync_workflow(agent: DubaiSyncAgent) -> Any:
    workflow = StateGraph(AgentState)
    workflow.add_node("discover_sources", agent.discover_sources_node)
    workflow.add_node("evaluate_delta", agent.evaluate_delta_node)
    workflow.add_node("extract_data", agent.extract_and_parse_node)
    workflow.add_node("upsert_graph", agent.upsert_knowledge_graph_node)

    workflow.add_edge(START, "discover_sources")
    workflow.add_edge("discover_sources", "evaluate_delta")
    workflow.add_conditional_edges(
        "evaluate_delta",
        route_conditional_sync,
        {"extract_data": "extract_data", "skip_sync": END},
    )
    workflow.add_edge("extract_data", "upsert_graph")
    workflow.add_edge("upsert_graph", END)
    return workflow.compile()
