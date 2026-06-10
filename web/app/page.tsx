import { fetchFacets, type Facets } from "@/lib/api";
import { SearchClient } from "@/components/SearchClient";

export default async function HomePage(): Promise<React.ReactElement> {
  let initialFacets: Facets | null = null;
  try {
    initialFacets = await fetchFacets();
  } catch {
    // SearchClient retries client-side if server-side fetch fails.
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Find a Dubai private school</h1>
        <p className="mt-1 text-sm text-muted dark:text-muted-dark">
          Filter by grade, budget, curriculum, location and KHDA rating — or ask
          the assistant. Results appear in the table below.
        </p>
      </div>
      <SearchClient initialFacets={initialFacets} />
    </div>
  );
}
