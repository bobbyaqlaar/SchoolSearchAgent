"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { type CompareRow, compareSchools } from "@/lib/api";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { DataTable } from "@/components/ui/DataTable";
import { Skeleton } from "@/components/ui/Skeleton";

export function ComparePageClient(): React.ReactElement {
  const searchParams = useSearchParams();
  const urlIds = useMemo(
    () =>
      searchParams
        .getAll("ids")
        .map((id) => id.trim())
        .filter(Boolean),
    [searchParams],
  );
  const [idsText, setIdsText] = useState<string>(() => urlIds.join(", "));
  const [rows, setRows] = useState<CompareRow[]>([]);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const runWithIds = useCallback(async (ids: string[]): Promise<void> => {
    if (ids.length === 0) {
      setError("Enter at least one school id.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setRows(await compareSchools(ids));
    } catch {
      setError("Comparison failed. Check the school ids and try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  async function run(): Promise<void> {
    const ids = idsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    await runWithIds(ids);
  }

  useEffect(() => {
    if (urlIds.length === 0) {
      return;
    }
    setIdsText(urlIds.join(", "));
    void runWithIds(urlIds);
  }, [urlIds, runWithIds]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Compare schools</h1>
      <p className="text-sm text-muted dark:text-muted-dark">
        Select schools from search results, or enter school ids manually
        (comma-separated).
      </p>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Input
          value={idsText}
          onChange={(e) => setIdsText(e.target.value)}
          placeholder="school-id-1, school-id-2"
          className="flex-1"
          aria-label="School ids"
        />
        <Button size="sm" onClick={run} disabled={loading}>
          {loading ? "Comparing…" : "Compare"}
        </Button>
      </div>

      {error && <ErrorState message={error} />}

      {loading && (
        <div className="space-y-2" role="status" aria-label="Loading comparison">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      )}

      {!loading && rows.length > 0 && (
        <DataTable
          caption="School comparison by area, rating and starting fee"
          headers={["School", "Area", "Rating", "From (AED)"]}
        >
          {rows.map((r) => (
            <tr
              key={r.school_name}
              className="border-b border-border dark:border-border-dark"
            >
              <td className="py-2">{r.school_name}</td>
              <td className="py-2">{r.location}</td>
              <td className="py-2">{r.latest_rating}</td>
              <td className="py-2">{r.min_fee?.toLocaleString() ?? "—"}</td>
            </tr>
          ))}
        </DataTable>
      )}
    </div>
  );
}
