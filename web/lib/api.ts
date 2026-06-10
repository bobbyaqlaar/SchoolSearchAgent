// Typed client for the KHDA FastAPI microservice. Types mirror the backend
// pydantic models / Envelope (the frozen wire contract).

const API_BASE: string =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface Envelope<T> {
  data: T;
  telemetry: Record<string, TelemetryEntry>;
}

export interface TelemetryEntry {
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface SchoolRow {
  school_id?: string;
  school_name: string;
  location: string;
  latest_rating: string;
  min_fee?: number | null;
  max_fee?: number | null;
  curriculums: string[];
}

/** @deprecated Use SchoolRow — kept for backward-compatible imports */
export type SearchResult = SchoolRow;

export interface Facets {
  curriculums: string[];
  neighborhoods: string[];
  ratings: string[];
  grades: string[];
}

export interface AskResponse {
  answer: string;
  model: string;
  schools: SchoolRow[];
}

export interface RatingEntry {
  academic_year: string;
  rating: string;
}

export interface FeeEntry {
  grade: string;
  tuition_fee: number;
}

export interface SchoolDetail {
  school_name: string;
  location: string;
  curriculums: string[];
  ratings: RatingEntry[];
  fees: FeeEntry[];
}

export interface CompareRow {
  school_name: string;
  location: string;
  latest_rating: string;
  min_fee: number;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    let detail = `API ${res.status}: ${path}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export async function fetchFacets(): Promise<Facets> {
  const env = await getJson<Envelope<Facets>>("/api/facets");
  return env.data;
}

export async function searchSchools(params: {
  grade?: string;
  maxBudget?: number;
  curriculum?: string;
  khdaRating?: string;
  neighborhood?: string;
}): Promise<SchoolRow[]> {
  const q = new URLSearchParams();
  if (params.grade) q.set("grade", params.grade);
  if (params.maxBudget !== undefined) {
    q.set("max_budget", String(params.maxBudget));
  }
  if (params.curriculum) q.set("curriculum", params.curriculum);
  if (params.khdaRating) q.set("khda_rating", params.khdaRating);
  if (params.neighborhood) q.set("neighborhood", params.neighborhood);
  const env = await getJson<Envelope<SchoolRow[]>>(
    `/api/schools/search?${q.toString()}`,
  );
  return env.data.map((row) => ({
    ...row,
    curriculums: row.curriculums ?? [],
  }));
}

export async function fetchSchoolDetail(id: string): Promise<SchoolDetail> {
  const env = await getJson<Envelope<SchoolDetail>>(`/api/schools/${id}`);
  return env.data;
}

export async function compareSchools(ids: string[]): Promise<CompareRow[]> {
  const q = new URLSearchParams();
  ids.forEach((id) => q.append("ids", id));
  const env = await getJson<Envelope<CompareRow[]>>(
    `/api/schools/compare?${q.toString()}`,
  );
  return env.data;
}

export async function fetchModels(): Promise<string[]> {
  return getJson<string[]>("/api/models");
}

export async function ask(
  question: string,
  selectedModel: string,
): Promise<Envelope<AskResponse>> {
  const res = await fetch(`${API_BASE}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, selected_model: selectedModel }),
  });
  if (!res.ok) {
    let detail = `API ${res.status}: /api/ask`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return (await res.json()) as Envelope<AskResponse>;
}

export { API_BASE };
