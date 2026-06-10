import { cn } from "@/lib/cn";

interface BadgeProps {
  children: React.ReactNode;
  className?: string;
  "aria-label"?: string;
}

export function Badge({
  children,
  className,
  "aria-label": ariaLabel,
}: BadgeProps): React.ReactElement {
  return (
    <span
      aria-label={ariaLabel}
      className={cn(
        "inline-flex shrink-0 items-center rounded bg-brand/10 px-2 py-0.5 text-xs font-medium text-brand",
        className,
      )}
    >
      {children}
    </span>
  );
}
