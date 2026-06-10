"""CLI entrypoint for the KHDA incremental sync pipeline."""

from __future__ import annotations

import argparse
import logging
import uuid
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig

from dubai.agent import DubaiSyncAgent, compile_sync_workflow
from dubai.graph_client import Neo4jClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dubai.cli")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KHDA knowledge-graph sync agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print configuration and exit without touching network or DB",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-sync every workbook school (ignores stored sync hash)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parse_args(argv)

    from dubai.settings import get_settings

    settings = get_settings()
    run_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("KHDA sync run %s @ %s", run_id, timestamp)

    if args.dry_run:
        logger.info("[dry-run] neo4j_uri=%s", settings.neo4j_uri)
        logger.info("[dry-run] no network or database calls performed")
        print("DRY RUN OK")
        return 0

    client = Neo4jClient()
    try:
        client.apply_constraints()
        agent = DubaiSyncAgent(client)
        app = compile_sync_workflow(agent)
        config = RunnableConfig(
            run_name=f"KHDA_Sync_{datetime.now():%Y-%m-%d}",
            tags=["scheduled-sync"],
            metadata={"run_id": run_id, "pipeline_version": "1.2.0"},
        )
        final_state = app.invoke(
            {
                "discovered_sources": [],
                "pending_syncs": [],
                "extracted_payloads": [],
                "audit_logs": {},
                "run_id": run_id,
                "force_resync": args.force,
            },
            config=config,
        )
        logs = final_state.get("audit_logs", {})
        print("\n================ RUN SUMMARY ================")
        print(f"Pending delta updates : {logs.get('initial_pending_count', 0)}")
        print(f"New schools created   : {logs.get('created', 0)}")
        print(f"Schools updated       : {logs.get('updated', 0)}")
        print(f"Validation failures   : {logs.get('validation_failures', 0)}")
        print(f"Parse failures        : {logs.get('extraction_failures', 0)}")
        print(f"Failures in dataset   : {logs.get('failures_recorded', 0)}")
        print("============================================")
        return 0
    except Exception as error:  # noqa: BLE001
        logger.error("Pipeline failure: %s", error)
        return 1
    finally:
        client.close()
        logger.info("Database session closed.")
