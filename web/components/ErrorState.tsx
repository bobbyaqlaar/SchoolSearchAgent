export function ErrorState({ message }: { message: string }): React.ReactElement {
  return (
    <div
      role="alert"
      className="rounded-lg border border-danger-border bg-danger-bg p-4 text-sm text-danger dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
    >
      {message}
    </div>
  );
}
