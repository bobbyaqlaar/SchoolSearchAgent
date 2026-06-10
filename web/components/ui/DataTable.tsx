interface DataTableProps {
  caption: string;
  headers: readonly string[];
  children: React.ReactNode;
}

export function DataTable({
  caption,
  headers,
  children,
}: DataTableProps): React.ReactElement {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border dark:border-border-dark">
            {headers.map((h) => (
              <th key={h} scope="col" className="py-2 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
