"use client";

import { cn } from "@/lib/utils";

type FilterOption = {
  value: string;
  label: string;
};

type UserFiltersProps = {
  role: string;
  status: string;
  roleOptions: FilterOption[];
  statusOptions: FilterOption[];
  onRoleChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onClear: () => void;
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

export function UserFilters({
  role,
  status,
  roleOptions,
  statusOptions,
  onRoleChange,
  onStatusChange,
  onClear,
  className,
}: UserFiltersProps) {
  const hasActiveFilters = role !== "all" || status !== "all";

  return (
    <div
      className={cn(
        "industrial-card grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3 lg:p-5",
        className,
      )}
    >
      <FilterSelect
        label="Role"
        value={role}
        options={roleOptions}
        onChange={onRoleChange}
      />
      <FilterSelect
        label="Status"
        value={status}
        options={statusOptions}
        onChange={onStatusChange}
      />
      <div className="flex items-end">
        <button
          type="button"
          disabled={!hasActiveFilters}
          onClick={onClear}
          className="h-10 w-full rounded-xl border border-border px-3 text-sm text-muted-foreground transition-industrial hover:bg-[var(--surface-secondary)] hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          Clear filters
        </button>
      </div>
    </div>
  );
}
