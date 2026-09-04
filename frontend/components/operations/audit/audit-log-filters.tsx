"use client";

import { cn } from "@/lib/utils";
import {
  AUDIT_ACTION_FILTER_OPTIONS,
  AUDIT_LOG_DEFAULT_FILTERS,
  type AuditLogFilterValues,
} from "@/lib/operations/constants";

type AuditLogFiltersProps = {
  filters: AuditLogFilterValues;
  onChange: (filters: AuditLogFilterValues) => void;
  className?: string;
};

const CONTROL_CLASS =
  "h-10 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-3 text-sm text-foreground transition-industrial focus-visible:border-[var(--accent-steel)]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-steel)]/15";

const LABEL_CLASS =
  "text-xs font-medium tracking-wide text-muted-foreground uppercase";

export function AuditLogFilters({
  filters,
  onChange,
  className,
}: AuditLogFiltersProps) {
  const hasActiveFilters =
    filters.action !== AUDIT_LOG_DEFAULT_FILTERS.action ||
    filters.dateFrom !== AUDIT_LOG_DEFAULT_FILTERS.dateFrom ||
    filters.dateTo !== AUDIT_LOG_DEFAULT_FILTERS.dateTo;

  return (
    <div
      className={cn(
        "industrial-card grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4 lg:p-5",
        className,
      )}
    >
      <div className="space-y-2">
        <label htmlFor="audit-action" className={LABEL_CLASS}>
          Action
        </label>
        <select
          id="audit-action"
          value={filters.action}
          onChange={(event) =>
            onChange({ ...filters, action: event.target.value })
          }
          className={CONTROL_CLASS}
        >
          {AUDIT_ACTION_FILTER_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label htmlFor="audit-date-from" className={LABEL_CLASS}>
          From
        </label>
        <input
          id="audit-date-from"
          type="date"
          value={filters.dateFrom}
          max={filters.dateTo || undefined}
          onChange={(event) =>
            onChange({ ...filters, dateFrom: event.target.value })
          }
          className={CONTROL_CLASS}
        />
      </div>

      <div className="space-y-2">
        <label htmlFor="audit-date-to" className={LABEL_CLASS}>
          To
        </label>
        <input
          id="audit-date-to"
          type="date"
          value={filters.dateTo}
          min={filters.dateFrom || undefined}
          onChange={(event) =>
            onChange({ ...filters, dateTo: event.target.value })
          }
          className={CONTROL_CLASS}
        />
      </div>

      <div className="flex items-end">
        <button
          type="button"
          disabled={!hasActiveFilters}
          onClick={() => onChange(AUDIT_LOG_DEFAULT_FILTERS)}
          className="h-10 w-full rounded-xl border border-border px-3 text-sm text-muted-foreground transition-industrial hover:bg-[var(--surface-secondary)] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
        >
          Clear filters
        </button>
      </div>
    </div>
  );
}
