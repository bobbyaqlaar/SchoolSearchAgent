import { cn } from "@/lib/cn";

const fieldBase =
  "rounded border border-border bg-surface px-2 py-1 text-sm text-slate-900 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand dark:border-border-dark dark:bg-slate-800 dark:text-slate-100";

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...props }: InputProps): React.ReactElement {
  return <input className={cn(fieldBase, className)} {...props} />;
}

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement>;

export function Select({
  className,
  children,
  ...props
}: SelectProps): React.ReactElement {
  return (
    <select className={cn(fieldBase, className)} {...props}>
      {children}
    </select>
  );
}
