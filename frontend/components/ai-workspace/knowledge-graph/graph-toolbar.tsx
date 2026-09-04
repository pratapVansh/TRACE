"use client";

import { useCallback, useRef, useState } from "react";
import { AlertCircle, Search, ZoomIn, ZoomOut, RotateCcw, Loader2 } from "lucide-react";

import type { EntityResponse } from "@/lib/api/graph";
import { searchEntities } from "@/lib/api/graph";
import { getApiErrorMessage } from "@/lib/api/errors";

type GraphToolbarProps = {
  onSearchResult: (entityId: string) => void;
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onReset?: () => void;
  onAddEntity?: (entity: EntityResponse) => void;
};

export function GraphToolbar({
  onSearchResult,
  onZoomIn,
  onZoomOut,
  onReset,
  onAddEntity,
}: GraphToolbarProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<EntityResponse[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [noResults, setNoResults] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearch = useCallback(
    async (q: string) => {
      setQuery(q);
      setSearchError(null);
      if (debounceRef.current) clearTimeout(debounceRef.current);

      if (q.trim().length < 1) {
        setResults([]);
        setShowDropdown(false);
        return;
      }

      debounceRef.current = setTimeout(async () => {
        setSearching(true);
        try {
          const data = await searchEntities(q.trim(), 0, 20);
          setResults(data.items);
          setNoResults(data.items.length === 0);
          setShowDropdown(true);
        } catch (err) {
          setResults([]);
          setNoResults(false);
          const msg = await getApiErrorMessage(err, "Search failed. Please try again.");
          setSearchError(msg);
        } finally {
          setSearching(false);
        }
      }, 300);
    },
    [],
  );

  const handleSelect = useCallback(
    (entity: EntityResponse) => {
      setQuery(entity.name);
      setShowDropdown(false);
      onSearchResult(entity.id);
      if (onAddEntity) onAddEntity(entity);
    },
    [onSearchResult, onAddEntity],
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Search */}
      <div className="relative flex-1 min-w-[200px] max-w-sm">
        <div className="relative">
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search entities..."
            className="w-full rounded-lg border border-border bg-[var(--surface-secondary)] py-2 pl-10 pr-4 text-sm text-foreground placeholder-muted-foreground outline-none transition-colors focus:border-primary/50 focus:ring-1 focus:ring-primary/25"
            onFocus={() => (results.length > 0 || noResults) && setShowDropdown(true)}
            onBlur={() => setTimeout(() => setShowDropdown(false), 300)}
          />
          {searching && (
            <Loader2
              size={14}
              className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-muted-foreground"
            />
          )}
        </div>

        {showDropdown && (
          <div
            className="absolute left-0 right-0 top-full z-50 mt-1 max-h-60 overflow-auto rounded-lg border border-border bg-[var(--surface-secondary)] shadow-xl"
            onMouseDown={(e) => e.preventDefault()}
          >
            {results.length > 0 ? (
              results.map((entity) => (
                <button
                  key={entity.id}
                  onMouseDown={() => handleSelect(entity)}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm text-foreground transition-colors hover:bg-border/50"
                >
                  <span className="shrink-0 rounded-full bg-border px-2 py-0.5 text-xs font-medium text-muted-foreground">
                    {entity.type}
                  </span>
                  <span className="truncate">{entity.name}</span>
                </button>
              ))
            ) : noResults ? (
              <div className="px-4 py-6 text-center text-xs text-muted-foreground">
                No entities found matching your search.
              </div>
            ) : null}
          </div>
        )}
      </div>

      {searchError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          <AlertCircle size={14} className="shrink-0" />
          <span>{searchError}</span>
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center gap-1 rounded-lg border border-border bg-[var(--surface-secondary)] p-1">
        <button
          onClick={onZoomIn}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-border/50 hover:text-foreground"
          aria-label="Zoom in"
          title="Zoom in"
        >
          <ZoomIn size={16} />
        </button>
        <button
          onClick={onZoomOut}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-border/50 hover:text-foreground"
          aria-label="Zoom out"
          title="Zoom out"
        >
          <ZoomOut size={16} />
        </button>
        <button
          onClick={onReset}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-border/50 hover:text-foreground"
          aria-label="Reset view"
          title="Reset view"
        >
          <RotateCcw size={16} />
        </button>
      </div>
    </div>
  );
}
