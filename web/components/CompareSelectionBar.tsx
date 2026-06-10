import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { buildCompareHref } from "@/lib/util";

interface CompareSelectionBarProps {
  selectedIds: readonly string[];
  onClear: () => void;
}

export function CompareSelectionBar({
  selectedIds,
  onClear,
}: CompareSelectionBarProps): React.ReactElement | null {
  if (selectedIds.length === 0) {
    return null;
  }

  const count = selectedIds.length;

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-wrap items-center gap-3 rounded-lg border border-brand/30 bg-brand/5 px-4 py-3 dark:border-brand/40 dark:bg-brand/10"
    >
      <p className="text-sm">
        {count} school{count === 1 ? "" : "s"} selected for comparison
      </p>
      <Link
        href={buildCompareHref(selectedIds)}
        className="inline-flex items-center justify-center rounded bg-brand px-4 py-1 text-sm font-medium text-white transition-all duration-200 ease-in-out hover:bg-brand-dark hover:scale-[1.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
      >
        Compare selected
      </Link>
      <Button type="button" variant="ghost" size="sm" onClick={onClear}>
        Clear
      </Button>
    </div>
  );
}
