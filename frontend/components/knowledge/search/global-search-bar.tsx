"use client";

import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type GlobalSearchBarProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  resultCount?: number;
  className?: string;
};

export function GlobalSearchBar({
  value,
  onChange,
  onSubmit,
  resultCount,
  className,
}: GlobalSearchBarProps) {
  return (
    <div className={cn("space-y-3", className)}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
        className="industrial-card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:p-5"
      >
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="Search procedures, assets, P&IDs, incident reports, equipment tags…"
            className="h-14 pl-12 text-base"
            aria-label="Global search"
          />
        </div>
        <button
          type="submit"
          className="h-14 shrink-0 rounded-xl bg-[var(--accent-steel)] px-8 text-sm font-medium text-white transition-industrial hover:bg-[#6a8eb5] sm:min-w-[140px]"
        >
          Search
        </button>
      </form>
      {resultCount !== undefined && value.trim() ? (
        <p className="text-sm text-muted-foreground">
          Found{" "}
          <span className="font-medium text-white">{resultCount}</span> matching
          document{resultCount === 1 ? "" : "s"} for &ldquo;{value.trim()}&rdquo;
        </p>
      ) : null}
    </div>
  );
}
