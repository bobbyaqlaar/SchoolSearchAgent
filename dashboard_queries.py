from neo4j import GraphDatabase

from dubai.curriculum import (
    matching_raw_curriculum_types,
    normalize_curriculum_list,
)


class DubaiDashboardEngine:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="password"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def _distinct_curriculum_types(self) -> list[str]:
        with self.driver.session() as session:
            return [
                rec["v"]
                for rec in session.run(
                    "MATCH (c:Curriculum) RETURN c.type AS v ORDER BY v  // curriculum types"
                )
            ]

    def _curriculum_filter_types(self, curriculum: str | None) -> list[str] | None:
        if not curriculum:
            return None
        return matching_raw_curriculum_types(
            self._distinct_curriculum_types(),
            curriculum,
        )

    def _normalize_result_rows(self, rows: list) -> list:
        for row in rows:
            row["curriculums"] = normalize_curriculum_list(row.get("curriculums") or [])
        return rows

    def search_filtered(
        self,
        *,
        max_budget: float | None = None,
        min_budget: float | None = None,
        grade: str | None = None,
        curriculum: str | None = None,
        khda_rating: str | None = None,
        neighborhood: str | None = None,
        limit: int = 100,
    ) -> list:
        """Multi-facet search returning tabular rows with fee range and curricula."""
        query = """
        MATCH (s:School)-[:LOCATED_IN]->(l:Location)
        MATCH (s)-[:RATED]->(r:InspectionRating)
        MATCH (s)-[:HAS_FEES]->(f:FeeStructure)
        WHERE ($max_budget IS NULL OR f.tuition_fee <= $max_budget)
          AND ($grade IS NULL OR f.grade = $grade)
          AND ($curriculum_types IS NULL OR EXISTS {
            MATCH (s)-[:OFFERS]->(c:Curriculum)
            WHERE c.type IN $curriculum_types
          })
          AND ($khda_rating IS NULL OR toLower(trim(r.rating)) = toLower(trim($khda_rating)))
          AND ($neighborhood IS NULL OR l.neighborhood = $neighborhood)
        WITH s, l, r, min(f.tuition_fee) AS min_fee, max(f.tuition_fee) AS max_fee
        WHERE ($min_budget IS NULL OR min_fee > $min_budget)
        OPTIONAL MATCH (s)-[:OFFERS]->(c:Curriculum)
        WITH s, l, r, min_fee, max_fee, collect(DISTINCT c.type) AS curriculums
        RETURN DISTINCT
            s.id AS school_id,
            s.name AS school_name,
            l.neighborhood AS location,
            r.rating AS latest_rating,
            min_fee,
            max_fee,
            curriculums
        ORDER BY latest_rating DESC, school_name ASC
        LIMIT $limit
        """
        curriculum_types = self._curriculum_filter_types(curriculum)
        with self.driver.session() as session:
            result = session.run(
                query,
                max_budget=float(max_budget) if max_budget is not None else None,
                min_budget=float(min_budget) if min_budget is not None else None,
                grade=grade,
                curriculum_types=curriculum_types,
                khda_rating=khda_rating,
                neighborhood=neighborhood,
                limit=int(limit),
            )
            return self._normalize_result_rows([record.data() for record in result])

    def search_by_specific_class(self, target_grade: str, max_budget: float, curriculum: str = None) -> list:
        """Grade-level search with consistent tabular row shape."""
        return self.search_filtered(
            max_budget=max_budget,
            grade=target_grade,
            curriculum=curriculum,
        )

    def search_schools(self, curriculum: str, max_budget: float, neighborhood: str = None) -> list:
        """
        Queries the knowledge graph for schools matching budget, curriculum, and area.
        """
        # Base query to traverse: Location <- School -> Curriculum & School -> Fees
        query = """
        MATCH (l:Location)<-[:LOCATED_IN]-(s:School)-[:OFFERS]->(c:Curriculum {type: $curriculum})
        MATCH (s)-[:HAS_FEES]->(f:FeeStructure)
        MATCH (s)-[:RATED]->(r:InspectionRating)
        
        WHERE f.tuition_fee <= $max_budget
          AND ($neighborhood IS NULL OR l.neighborhood = $neighborhood)
          
        RETURN DISTINCT 
            s.name AS school_name,
            l.neighborhood AS location,
            r.rating AS latest_rating,
            collect({grade: f.grade, fee: f.tuition_fee}) AS qualifying_grades
        ORDER BY latest_rating DESC, school_name ASC
        """
        
        with self.driver.session() as session:
            result = session.run(query, curriculum=curriculum, max_budget=float(max_budget), neighborhood=neighborhood)
            return [record.data() for record in result]

    def search_by_budget_and_rating(
        self,
        max_budget: float,
        khda_rating: str,
        *,
        curriculum: str | None = None,
        neighborhood: str | None = None,
        limit: int = 50,
    ) -> list:
        """Schools with any fee tier <= max_budget and matching KHDA DSIB rating."""
        return self.search_filtered(
            max_budget=max_budget,
            khda_rating=khda_rating,
            curriculum=curriculum,
            neighborhood=neighborhood,
            limit=limit,
        )

    def find_school_by_name(self, name: str) -> dict | None:
        """Best-effort name lookup for chat tools (case-insensitive contains match)."""
        query = """
        MATCH (s:School)
        WHERE toLower(s.name) CONTAINS toLower($name)
        OPTIONAL MATCH (s)-[:LOCATED_IN]->(l:Location)
        OPTIONAL MATCH (s)-[:OFFERS]->(c:Curriculum)
        OPTIONAL MATCH (s)-[:RATED]->(r:InspectionRating)
        OPTIONAL MATCH (s)-[:HAS_FEES]->(f:FeeStructure)
        WITH s, l,
             collect(DISTINCT c.type) AS curriculums,
             head(collect(DISTINCT {academic_year: r.academic_year, rating: r.rating})) AS latest,
             min(f.tuition_fee) AS min_fee,
             max(f.tuition_fee) AS max_fee
        RETURN
            s.id AS school_id,
            s.name AS school_name,
            l.neighborhood AS location,
            curriculums,
            latest.rating AS latest_rating,
            latest.academic_year AS rating_year,
            min_fee,
            max_fee
        ORDER BY size(s.name) ASC
        LIMIT 1
        """
        with self.driver.session() as session:
            record = session.run(query, name=name.strip()).single()
            if not record:
                return None
            row = record.data()
            row["curriculums"] = normalize_curriculum_list(row.get("curriculums") or [])
            return row

    def get_school_detail(self, school_id: str) -> dict | None:
        """Full profile: curricula, latest inspection rating, and complete fee list."""
        query = """
        MATCH (s:School {id: $school_id})
        OPTIONAL MATCH (s)-[:LOCATED_IN]->(l:Location)
        OPTIONAL MATCH (s)-[:OFFERS]->(c:Curriculum)
        OPTIONAL MATCH (s)-[:RATED]->(r:InspectionRating)
        OPTIONAL MATCH (s)-[:HAS_FEES]->(f:FeeStructure)
        RETURN
            s.name AS school_name,
            l.neighborhood AS location,
            collect(DISTINCT c.type) AS curriculums,
            collect(DISTINCT {academic_year: r.academic_year, rating: r.rating}) AS ratings,
            collect(DISTINCT {grade: f.grade, tuition_fee: f.tuition_fee}) AS fees
        """
        with self.driver.session() as session:
            record = session.run(query, school_id=school_id).single()
            if not record:
                return None
            detail = record.data()
            detail["curriculums"] = normalize_curriculum_list(detail.get("curriculums") or [])
            return detail

    def compare_schools(self, school_ids: list) -> list:
        """Aligned comparison rows for multiple schools."""
        query = """
        MATCH (s:School)-[:LOCATED_IN]->(l:Location)
        WHERE s.id IN $ids
        OPTIONAL MATCH (s)-[:RATED]->(r:InspectionRating)
        OPTIONAL MATCH (s)-[:HAS_FEES]->(f:FeeStructure)
        RETURN
            s.name AS school_name,
            l.neighborhood AS location,
            head(collect(DISTINCT r.rating)) AS latest_rating,
            min(f.tuition_fee) AS min_fee
        ORDER BY school_name ASC
        """
        with self.driver.session() as session:
            return [record.data() for record in session.run(query, ids=school_ids)]

    def facets(self) -> dict:
        """Distinct curriculums, neighborhoods, and ratings for filter UIs."""
        with self.driver.session() as session:
            curriculums = [
                rec["v"]
                for rec in session.run(
                    "MATCH (c:Curriculum) RETURN c.type AS v ORDER BY v  // curriculums"
                )
            ]
            neighborhoods = [
                rec["v"]
                for rec in session.run(
                    "MATCH (l:Location) RETURN l.neighborhood AS v ORDER BY v  // neighborhoods"
                )
            ]
            ratings = [
                rec["v"]
                for rec in session.run(
                    "MATCH (r:InspectionRating) RETURN DISTINCT r.rating AS v ORDER BY v  // ratings"
                )
            ]
            grades = [
                rec["v"]
                for rec in session.run(
                    "MATCH (f:FeeStructure) RETURN DISTINCT f.grade AS v ORDER BY v  // grades"
                )
            ]
        return {
            "curriculums": normalize_curriculum_list(curriculums),
            "neighborhoods": neighborhoods,
            "ratings": ratings,
            "grades": grades,
        }


# ==========================================
# RUNNING SAMPLE QUERIES
# ==========================================
if __name__ == "__main__":
    # Open dashboard portal connection
    dashboard = DubaiDashboardEngine(uri="bolt://localhost:7687", user="neo4j", password="password")
    
    print("\n🔍 SEARCH: British Curriculum, under 65,000 AED across all Dubai:")
    results = dashboard.search_schools(curriculum="UK", max_budget=65000)
    
    for school in results[:5]:  # Show top 5 matches
        print(f"\n🏫 School: {school['school_name']} | Location: {school['location']} | Rating: {school['latest_rating']}")
        print("   Available Grades under budget:")
        for grade_info in school['qualifying_grades'][:2]:
            print(f"   - {grade_info['grade']}: AED {grade_info['fee']:,}")
            
    print("\n🔍 SEARCH: IB Curriculum, under 80,000 AED in Mirdif neighborhood specifically:")
    mirdif_results = dashboard.search_schools(curriculum="IB", max_budget=80000, neighborhood="Mirdif")
    
    if not mirdif_results:
        print("   No matching schools found for this specific area combo.")
    else:
        for school in mirdif_results:
            print(f"   - {school['school_name']} (Rated: {school['latest_rating']})")

    dashboard.close()

