import { cn } from "@/lib/cn";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps): React.ReactElement {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded bg-slate-200 dark:bg-slate-800",
        className,
      )}
    />
  );
}

interface SkeletonGridProps {
  count?: number;
  cardClassName?: string;
}

export function SkeletonGrid({
  count = 6,
  cardClassName = "h-28",
}: SkeletonGridProps): React.ReactElement {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Loading results"
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
    >
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className={cn("rounded-lg", cardClassName)} />
      ))}
    </div>
  );
}
