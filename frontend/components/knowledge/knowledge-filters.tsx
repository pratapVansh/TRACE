"use client";

import { cn } from "@/lib/utils";

export type FilterValues = {
  type: string;
  status: string;
  department: string;
};

type FilterOption = {
  value: string;
  label: string;
};

type KnowledgeFiltersProps = {
  filters: FilterValues;
  onChange: (filters: FilterValues) => void;
  typeOptions: FilterOption[];
  statusOptions: FilterOption[];
  departmentOptions?: FilterOption[];
  typeLabel?: string;
  statusLabel?: string;
  departmentLabel?: string;
  resetFilters?: FilterValues;
  className?: string;
};

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <label className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </label>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-3 text-sm text-foreground transition-industrial focus-visible:border-[var(--accent-steel)]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-steel)]/15"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export function KnowledgeFilters({
  filters,
  onChange,
  typeOptions,
  statusOptions,
  departmentOptions,
  typeLabel = "Document Type",
  statusLabel = "Status",
  departmentLabel = "Department",
  resetFilters = DEFAULT_FILTERS,
  className,
}: KnowledgeFiltersProps) {
  const showDepartmentFilter = departmentOptions !== undefined;
  const hasActiveFilters =
    filters.type !== resetFilters.type ||
    filters.status !== resetFilters.status ||
    (showDepartmentFilter && filters.department !== resetFilters.department);

  return (
    <div
      className={cn(
        "industrial-card grid gap-4 p-4 sm:grid-cols-2 lg:p-5",
        showDepartmentFilter ? "lg:grid-cols-4" : "lg:grid-cols-3",
        className,
      )}
    >
      <FilterSelect
        label={typeLabel}
        value={filters.type}
        options={typeOptions}
        onChange={(type) => onChange({ ...filters, type })}
      />
      <FilterSelect
        label={statusLabel}
        value={filters.status}
        options={statusOptions}
        onChange={(status) => onChange({ ...filters, status })}
      />
      {showDepartmentFilter ? (
        <FilterSelect
          label={departmentLabel}
          value={filters.department}
          options={departmentOptions}
          onChange={(department) => onChange({ ...filters, department })}
        />
      ) : null}
      <div className="flex items-end">
        <button
          type="button"
          disabled={!hasActiveFilters}
          onClick={() => onChange(resetFilters)}
          className="h-10 w-full rounded-xl border border-border px-3 text-sm text-muted-foreground transition-industrial hover:bg-[var(--surface-secondary)] hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          Clear filters
        </button>
      </div>
    </div>
  );
}

export const DEFAULT_FILTERS: FilterValues = {
  type: "all",
  status: "all",
  department: "all",
};
