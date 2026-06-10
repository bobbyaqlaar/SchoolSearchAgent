import Link from "next/link";
import type { SchoolRow } from "@/lib/api";
import { formatFeeRange, slugify } from "@/lib/util";
import { Badge } from "@/components/ui/Badge";

export function SchoolCard({ result }: { result: SchoolRow }): React.ReactElement {
  const href = result.school_id
    ? `/schools/${result.school_id}`
    : `/schools/${slugify(result.school_name)}`;

  return (
    <Link
      href={href}
      className="block rounded-lg border border-border bg-surface p-4 shadow-sm transition-all duration-200 ease-in-out hover:scale-[1.02] hover:border-brand hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface dark:border-border-dark dark:bg-surface-dark dark:focus-visible:ring-offset-surface-dark"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold">{result.school_name}</h3>
        <Badge aria-label={`KHDA rating: ${result.latest_rating}`}>
          {result.latest_rating}
        </Badge>
      </div>
      <p className="mt-1 text-sm text-muted dark:text-muted-dark">{result.location}</p>
      <p className="mt-2 text-sm">
        Fee range:{" "}
        <span className="font-semibold">
          {formatFeeRange(result.min_fee, result.max_fee)}
        </span>
      </p>
    </Link>
  );
}
