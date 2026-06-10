"use client";

import { useCallback, useEffect, useState } from "react";
import {
  type Facets,
  type SchoolRow,
  fetchFacets,
  searchSchools,
} from "@/lib/api";
import { AskPanel } from "@/components/AskPanel";
import { CompareSelectionBar } from "@/components/CompareSelectionBar";
import { ErrorState } from "@/components/ErrorState";
import { SchoolResultsTable } from "@/components/SchoolResultsTable";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { MAX_COMPARE_SCHOOLS } from "@/lib/util";

type ResultSource = "search" | "assistant" | null;

interface SearchClientProps {
  initialFacets?: Facets | null;
}

export function SearchClient({
  initialFacets = null,
}: SearchClientProps): React.ReactElement {
  const [facets, setFacets] = useState<Facets | null>(initialFacets);
  const [facetsLoading, setFacetsLoading] = useState(initialFacets === null);
  const [grade, setGrade] = useState<string>("");
  const [curriculum, setCurriculum] = useState<string>("");
  const [khdaRating, setKhdaRating] = useState<string>("");
  const [location, setLocation] = useState<string>("");
  const [maxBudget, setMaxBudget] = useState<string>("");
  const [results, setResults] = useState<SchoolRow[]>([]);
  const [resultSource, setResultSource] = useState<ResultSource>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [compareIds, setCompareIds] = useState<Set<string>>(() => new Set());

  const toggleCompare = useCallback((schoolId: string): void => {
    setCompareIds((prev) => {
      const next = new Set(prev);
      if (next.has(schoolId)) {
        next.delete(schoolId);
      } else if (next.size < MAX_COMPARE_SCHOOLS) {
        next.add(schoolId);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (initialFacets !== null) {
      return;
    }
    setFacetsLoading(true);
    fetchFacets()
      .then(setFacets)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "";
        if (msg.includes("7687") || /neo4j|database failure/i.test(msg)) {
          const isLocal =
            typeof window !== "undefined" &&
            (window.location.hostname === "localhost" ||
              window.location.hostname === "127.0.0.1");
          setError(
            isLocal
              ? "Neo4j is not reachable. Start Docker Desktop, then from the project root run: docker compose up neo4j -d"
              : "School database is unavailable. The API cannot reach Neo4j — check NEO4J_URI on Cloud Run (must be your Aura URI, not localhost).",
          );
          return;
        }
        if (/failed to fetch|networkerror|load failed/i.test(msg)) {
          const isLocal =
            typeof window !== "undefined" &&
            (window.location.hostname === "localhost" ||
              window.location.hostname === "127.0.0.1");
          setError(
            isLocal
              ? "Could not reach the API. From the project root run: uv run uvicorn api_service:app --reload"
              : "Could not reach the API. Check that Cloud Run services dubai-api and dubai-web are deployed and healthy.",
          );
          return;
        }
        setError("Could not load filter options. Is the API running?");
      })
      .finally(() => setFacetsLoading(false));
  }, [initialFacets]);

  const facetPlaceholder = facetsLoading ? "Loading filters…" : "Any grade";
  const curriculumPlaceholder = facetsLoading ? "Loading filters…" : "Any curriculum";
  const ratingPlaceholder = facetsLoading ? "Loading filters…" : "Any rating";
  const locationPlaceholder = facetsLoading ? "Loading filters…" : "Any location";

  async function runSearch(): Promise<void> {
    setLoading(true);
    setError("");
    try {
      const budget =
        maxBudget.trim() === "" ? undefined : Number.parseFloat(maxBudget);
      if (budget !== undefined && Number.isNaN(budget)) {
        setError("Enter a valid max annual budget in AED.");
        setLoading(false);
        return;
      }
      const data = await searchSchools({
        grade: grade || undefined,
        maxBudget: budget,
        curriculum: curriculum || undefined,
        khdaRating: khdaRating || undefined,
        neighborhood: location || undefined,
      });
      setResults(data);
      setResultSource("search");
    } catch {
      setError("We couldn't complete that search right now. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function handleAssistantResults(schools: SchoolRow[]): void {
    setResults(schools);
    setResultSource("assistant");
    setError("");
  }

  return (
    <div className="space-y-6">
      <section
        aria-labelledby="search-filters-heading"
        className="rounded-lg border border-border bg-surface p-4 dark:border-border-dark dark:bg-surface-dark"
      >
        <h2 id="search-filters-heading" className="text-lg font-semibold">
          Search schools
        </h2>
        <p className="mt-1 text-sm text-muted dark:text-muted-dark">
          Filter by grade, curriculum, KHDA rating, location, and max annual
          budget (AED).
        </p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1 text-sm">
            Grade
            <Select
              key={facets ? "grade-loaded" : "grade-loading"}
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
              aria-label="Grade"
              disabled={facetsLoading}
            >
              <option value="">{facetPlaceholder}</option>
              {facets?.grades.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </Select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Curriculum
            <Select
              key={facets ? "curriculum-loaded" : "curriculum-loading"}
              value={curriculum}
              onChange={(e) => setCurriculum(e.target.value)}
              aria-label="Curriculum"
              disabled={facetsLoading}
            >
              <option value="">{curriculumPlaceholder}</option>
              {facets?.curriculums.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            KHDA rating
            <Select
              key={facets ? "rating-loaded" : "rating-loading"}
              value={khdaRating}
              onChange={(e) => setKhdaRating(e.target.value)}
              aria-label="KHDA rating"
              disabled={facetsLoading}
            >
              <option value="">{ratingPlaceholder}</option>
              {facets?.ratings.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Location
            <Select
              key={facets ? "location-loaded" : "location-loading"}
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              aria-label="Location"
              disabled={facetsLoading}
            >
              <option value="">{locationPlaceholder}</option>
              {facets?.neighborhoods.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </Select>
          </label>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto]">
          <label className="flex flex-col gap-1 text-sm">
            Max annual budget (AED)
            <Input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={maxBudget}
              onChange={(e) => setMaxBudget(e.target.value)}
              placeholder="e.g. 90000"
              aria-label="Max annual budget in AED"
            />
          </label>
          <div className="flex items-end">
            <Button
              onClick={runSearch}
              disabled={loading || facetsLoading}
              className="w-full transition-all duration-200 ease-in-out hover:scale-[1.02] active:scale-[0.98] sm:w-auto sm:min-w-[8rem]"
            >
              {loading ? "Searching…" : "Search"}
            </Button>
          </div>
        </div>
      </section>

      <AskPanel onSchoolResults={handleAssistantResults} />

      {error && <ErrorState message={error} />}

      <section aria-labelledby="results-heading" className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="results-heading" className="text-lg font-semibold">
            Results
          </h2>
          {resultSource && !loading && (
            <p className="text-xs text-muted dark:text-muted-dark">
              {resultSource === "search"
                ? "From filter search"
                : "From assistant"}
              {" · "}
              {results.length} school{results.length === 1 ? "" : "s"}
            </p>
          )}
        </div>

        {loading ? (
          <div className="space-y-2" role="status" aria-label="Loading results">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : resultSource ? (
          <>
            <CompareSelectionBar
              selectedIds={[...compareIds]}
              onClear={() => setCompareIds(new Set())}
            />
            <SchoolResultsTable
              rows={results}
              compareSelectedIds={compareIds}
              onCompareToggle={toggleCompare}
            />
          </>
        ) : null}

        {!loading && !resultSource && !error && (
          <p className="text-sm text-muted dark:text-muted-dark">
            Use the filters above or ask the assistant to see matching schools.
          </p>
        )}
      </section>
    </div>
  );
}
