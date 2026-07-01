import type { ReactNode } from "react";

type DataTableColumn<T> = {
  key: string;
  header: string;
  className?: string;
  render: (row: T) => ReactNode;
};

type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  data: T[];
  rowKey: (row: T) => string;
  emptyMessage?: string;
  footer?: ReactNode;
  minWidth?: string;
};

export function DataTable<T>({
  columns,
  data,
  rowKey,
  emptyMessage = "No records found.",
  footer,
  minWidth = "800px",
}: DataTableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="industrial-card flex flex-col items-center justify-center p-12 text-center">
        <p className="text-sm text-muted-foreground">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="industrial-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm" style={{ minWidth }}>
          <thead>
            <tr className="border-b border-border bg-[var(--surface-secondary)]/60">
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`px-4 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase first:pl-6 last:pr-6 ${column.className ?? ""}`}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr
                key={rowKey(row)}
                className="border-b border-border/70 transition-industrial last:border-0 hover:bg-[var(--surface-secondary)]/40"
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`px-4 py-4 first:pl-6 last:pr-6 ${column.className ?? ""}`}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {footer ? (
        <div className="border-t border-border px-6 py-3 text-xs text-muted-foreground">
          {footer}
        </div>
      ) : null}
    </div>
  );
}
