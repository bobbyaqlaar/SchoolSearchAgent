"""Neo4j persistence client with idempotent MERGE writes.

The Cypher below is the corrected version of the original (which had an
unclosed string and an in-string ``session.run``). One properly terminated
MERGE statement writes School + Location + Curriculum + InspectionRating, then
UNWINDs fees into individual FeeStructure nodes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from dubai.schemas import SchoolDataModel
from dubai.settings import get_settings

_CONSTRAINTS_FILE = Path(__file__).resolve().parent.parent / "scripts" / "init_constraints.cypher"

# FOREACH is used for the list relationships instead of UNWIND: UNWIND on an
# empty list collapses the whole statement pipeline (so later MERGEs silently do
# not run), whereas FOREACH over an empty list is a safe no-op.
_UPSERT_CYPHER = """
MERGE (s:School {id: $school_id})
SET s.name = $name,
    s.last_sync_hash = $sync_hash
WITH s
OPTIONAL MATCH (s)-[:HAS_FEES]->(f:FeeStructure)
DETACH DELETE f
WITH s
MERGE (l:Location {neighborhood: $neighborhood})
ON CREATE SET l.city = 'Dubai'
MERGE (s)-[:LOCATED_IN]->(l)

MERGE (r:InspectionRating {id: $school_id + '_' + $academic_year})
SET r.academic_year = $academic_year,
    r.rating = $khda_rating
MERGE (s)-[:RATED]->(r)

FOREACH (curr_name IN $curriculums |
    MERGE (c:Curriculum {type: curr_name})
    MERGE (s)-[:OFFERS]->(c)
)

FOREACH (fee_item IN $fees |
    MERGE (f:FeeStructure {id: $school_id + '_' + fee_item.grade})
    SET f.grade = fee_item.grade,
        f.tuition_fee = toFloat(fee_item.tuition_fee),
        f.currency = 'AED',
        f.last_updated_timestamp = datetime()
    MERGE (s)-[:HAS_FEES]->(f)
)
"""


class Neo4jClient:
    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        *,
        driver: Any = None,
    ) -> None:
        if driver is not None:
            self.driver = driver
        else:
            settings = get_settings()
            self.driver = GraphDatabase.driver(
                uri or settings.neo4j_uri,
                auth=(user or settings.neo4j_user, password or settings.neo4j_password),
            )

    def close(self) -> None:
        self.driver.close()

    def apply_constraints(self) -> None:
        raw = _CONSTRAINTS_FILE.read_text(encoding="utf-8")
        # Drop full-line comments first, then split into statements.
        code = "\n".join(
            line for line in raw.splitlines() if not line.strip().startswith("//")
        )
        statements = [stmt.strip() for stmt in code.split(";") if stmt.strip()]
        with self.driver.session() as session:
            for statement in statements:
                session.run(statement)

    def school_exists(self, school_id: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (s:School {id: $id}) RETURN s", id=school_id
            ).single()
            return result is not None

    def get_sync_hash(self, school_id: str) -> str | None:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (s:School {id: $id}) RETURN s.last_sync_hash AS h", id=school_id
            ).single()
            return result["h"] if result else None

    def clear_school_fees(self, school_id: str) -> None:
        """Remove stale fee nodes when a school no longer passes validation."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (s:School {id: $school_id})-[:HAS_FEES]->(f:FeeStructure)
                DETACH DELETE f
                """,
                school_id=school_id,
            )

    def upsert_school(self, data: SchoolDataModel, *, sync_hash: str) -> bool:
        """Idempotently MERGE a school graph. Returns True when newly created."""
        created = not self.school_exists(data.school_id)
        with self.driver.session() as session:
            session.run(
                _UPSERT_CYPHER,
                school_id=data.school_id,
                name=data.name,
                sync_hash=sync_hash,
                neighborhood=data.neighborhood,
                curriculums=data.curriculums,
                academic_year=data.academic_year,
                khda_rating=data.khda_rating,
                fees=[fee.model_dump() for fee in data.fees],
            )
        return created
