// Enforce unique identification across all core nodes
CREATE CONSTRAINT unique_school_id IF NOT EXISTS FOR (s:School) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT unique_location_neighborhood IF NOT EXISTS FOR (l:Location) REQUIRE l.neighborhood IS UNIQUE;
CREATE CONSTRAINT unique_curriculum_type IF NOT EXISTS FOR (c:Curriculum) REQUIRE c.type IS UNIQUE;
CREATE CONSTRAINT unique_inspection_id IF NOT EXISTS FOR (r:InspectionRating) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT unique_fee_id IF NOT EXISTS FOR (f:FeeStructure) REQUIRE f.id IS UNIQUE;
// Accelerate numerical budget-range lookups across class fee instances
CREATE INDEX fee_lookup_range_idx IF NOT EXISTS FOR (f:FeeStructure) ON (f.tuition_fee, f.grade);
