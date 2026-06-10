import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { DataTable } from "@/components/ui/DataTable";
import { type SchoolRow } from "@/lib/api";
import {
  MAX_COMPARE_SCHOOLS,
  formatFeeRange,
  resolveSchoolId,
} from "@/lib/util";

interface SchoolResultsTableProps {
  rows: SchoolRow[];
  caption?: string;
  compareSelectedIds?: ReadonlySet<string>;
  onCompareToggle?: (schoolId: string) => void;
}

export function SchoolResultsTable({
  rows,
  caption = "School search results",
  compareSelectedIds,
  onCompareToggle,
}: SchoolResultsTableProps): React.ReactElement {
  const compareEnabled =
    compareSelectedIds !== undefined && onCompareToggle !== undefined;
  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted dark:text-muted-dark">
        No schools matched your criteria.
      </p>
    );
  }

  return (
    <DataTable
      caption={caption}
      headers={
        compareEnabled
          ? [
              "Compare",
              "School name",
              "Location",
              "KHDA rating",
              "Fee range",
              "Curriculum",
            ]
          : [
              "School name",
              "Location",
              "KHDA rating",
              "Fee range",
              "Curriculum",
            ]
      }
    >
      {rows.map((row) => {
        const schoolId = resolveSchoolId(row.school_id, row.school_name);
        const href = `/schools/${schoolId}`;
        const isSelected = compareSelectedIds?.has(schoolId) ?? false;
        const atLimit =
          compareEnabled &&
          !isSelected &&
          (compareSelectedIds?.size ?? 0) >= MAX_COMPARE_SCHOOLS;
        return (
          <tr
            key={schoolId}
            className="border-b border-border transition-colors hover:bg-brand/5 dark:border-border-dark"
          >
            {compareEnabled && (
              <td className="py-3 pr-4">
                <input
                  type="checkbox"
                  checked={isSelected}
                  disabled={atLimit}
                  onChange={() => onCompareToggle(schoolId)}
                  aria-label={`Compare ${row.school_name}`}
                  className="size-4 rounded border-border text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-not-allowed disabled:opacity-50"
                />
              </td>
            )}
            <td className="py-3 pr-4 font-medium">
              <Link
                href={href}
                className="text-brand underline-offset-2 transition-all duration-200 ease-in-out hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              >
                {row.school_name}
              </Link>
            </td>
            <td className="py-3 pr-4 text-muted dark:text-muted-dark">
              {row.location || "—"}
            </td>
            <td className="py-3 pr-4">{row.latest_rating || "—"}</td>
            <td className="py-3 pr-4 tabular-nums">
              {formatFeeRange(row.min_fee, row.max_fee)}
            </td>
            <td className="py-3">
              <div className="flex flex-wrap gap-1">
                {row.curriculums.length > 0 ? (
                  row.curriculums.map((c) => (
                    <Badge key={c} aria-label={`Curriculum ${c}`}>
                      {c}
                    </Badge>
                  ))
                ) : (
                  <span className="text-muted dark:text-muted-dark">—</span>
                )}
              </div>
            </td>
          </tr>
        );
      })}
    </DataTable>
  );
}
