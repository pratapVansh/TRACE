"use client";

import { X } from "lucide-react";

import { cn } from "@/lib/utils";
import type { SearchFilter } from "@/types/knowledge";

const DOC_TYPE_OPTIONS = [
  { value: "", label: "All types" },
  { value: "manual", label: "Manual" },
  { value: "sop", label: "SOP" },
  { value: "spreadsheet", label: "Spreadsheet" },
  { value: "document", label: "Document" },
  { value: "image", label: "Image" },
  { value: "incident_report", label: "Incident Report" },
  { value: "inspection_report", label: "Inspection Report" },
  { value: "maintenance_log", label: "Maintenance Log" },
  { value: "safety_manual", label: "Safety Manual" },
];

const LANGUAGE_OPTIONS = [
  { value: "", label: "All languages" },
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "pt", label: "Portuguese" },
  { value: "zh", label: "Chinese" },
  { value: "ar", label: "Arabic" },
];

export const DEFAULT_SEARCH_FILTERS: SearchFilter = {};

type SearchFiltersPanelProps = {
  filters: SearchFilter;
  onChange: (filters: SearchFilter) => void;
  className?: string;
};

export function SearchFiltersPanel({
  filters,
  onChange,
  className,
}: SearchFiltersPanelProps) {
  const hasActiveFilters = Object.values(filters).some(
    (v) => v !== undefined && v !== "",
  );

  return (
    <div
      className={cn(
        "industrial-card grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3 lg:p-5",
        className,
      )}
    >
      <FilterSelect
        label="Document Type"
        value={filters.document_type ?? ""}
        options={DOC_TYPE_OPTIONS}
        onChange={(v) => onChange({ ...filters, document_type: v || undefined })}
      />

      <FilterSelect
        label="Language"
        value={filters.language ?? ""}
        options={LANGUAGE_OPTIONS}
        onChange={(v) => onChange({ ...filters, language: v || undefined })}
      />

      <div className="space-y-2">
        <label className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Filename
        </label>
        <input
          type="text"
          value={filters.filename ?? ""}
          onChange={(e) =>
            onChange({ ...filters, filename: e.target.value || undefined })
          }
          placeholder="Filter by filename…"
          className="h-10 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-3 text-sm text-foreground placeholder:text-muted-foreground/50 transition-industrial focus-visible:border-[var(--accent-steel)]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-steel)]/15"
        />
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Uploaded after
        </label>
        <input
          type="date"
          value={filters.uploaded_after ?? ""}
          onChange={(e) =>
            onChange({ ...filters, uploaded_after: e.target.value || undefined })
          }
          className="h-10 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-3 text-sm text-foreground transition-industrial focus-visible:border-[var(--accent-steel)]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-steel)]/15"
        />
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Uploaded before
        </label>
        <input
          type="date"
          value={filters.uploaded_before ?? ""}
          onChange={(e) =>
            onChange({ ...filters, uploaded_before: e.target.value || undefined })
          }
          className="h-10 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-3 text-sm text-foreground transition-industrial focus-visible:border-[var(--accent-steel)]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-steel)]/15"
        />
      </div>

      <div className="flex items-end">
        <button
          type="button"
          disabled={!hasActiveFilters}
          onClick={() => onChange(DEFAULT_SEARCH_FILTERS)}
          className="inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-xl border border-border px-3 text-sm text-muted-foreground transition-industrial hover:bg-[var(--surface-secondary)] hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          <X className="size-4" />
          Clear filters
        </button>
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <label className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-3 text-sm text-foreground transition-industrial focus-visible:border-[var(--accent-steel)]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-steel)]/15"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
