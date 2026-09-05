"use client";

import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { fetchHealth } from "@/lib/api/health";
import type { HealthResponse } from "@/types/api";

const LABELS: Record<string, string> = {
  database: "Database",
  vector_store: "Vector store",
  graph_store: "Knowledge graph",
  llm: "Copilot model",
  reranker: "Reranker",
};

export function BackendStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    void fetchHealth()
      .then(setHealth)
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return (
      <div className="space-y-4 rounded-xl border border-border bg-[var(--surface-secondary)] p-5">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-7 w-24" />
        <Skeleton className="h-4 w-40" />
      </div>
    );
  }

  // A reachable backend running without its reranker or graph store is neither
  // "Online" nor "Offline". Collapsing the three states into a boolean is what
  // let a silently degraded deployment read as healthy.
  const reachable = health !== null;
  const degraded = health?.status === "degraded" || health?.status === "unavailable";
  const impaired = health?.degraded ?? [];

  const badge = !reachable ? "Offline" : degraded ? "Degraded" : "Online";
  const badgeVariant = !reachable ? "warning" : degraded ? "warning" : "success";
  const headline = !reachable
    ? "Connection unavailable"
    : health?.status === "unavailable"
      ? "Core service unavailable"
      : degraded
        ? "Running degraded"
        : "Systems operational";

  return (
    <div className="rounded-xl border border-border bg-[var(--surface-secondary)] p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">
          Backend connectivity
        </p>
        <Badge variant={badgeVariant}>{badge}</Badge>
      </div>
      <p className="mt-4 text-2xl font-semibold text-foreground">{headline}</p>
      {health?.service ? (
        <p className="mt-2 text-sm text-muted-foreground">{health.service}</p>
      ) : null}

      {impaired.length > 0 && (
        <ul className="mt-4 space-y-2 border-t border-border pt-3">
          {impaired.map((name) => (
            <li key={name} className="text-[12px] leading-snug">
              <span className="font-medium text-foreground">
                {LABELS[name] ?? name}
              </span>
              <span className="text-muted-foreground">
                {" — "}
                {health?.components?.[name]?.detail ?? "unavailable"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
