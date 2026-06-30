"use client";

import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { fetchHealth } from "@/lib/api/health";
import type { HealthResponse } from "@/types/api";

export function BackendStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    void fetchHealth()
      .then(setHealth)
      .finally(() => setIsLoading(false));
  }, []);

  const isOnline = health?.status === "ok";

  if (isLoading) {
    return (
      <div className="space-y-4 rounded-xl border border-border bg-[var(--surface-secondary)] p-5">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-7 w-24" />
        <Skeleton className="h-4 w-40" />
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-[var(--surface-secondary)] p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">
          Backend connectivity
        </p>
        <Badge variant={isOnline ? "success" : "warning"}>
          {isOnline ? "Online" : "Offline"}
        </Badge>
      </div>
      <p className="mt-4 text-2xl font-semibold text-white">
        {isOnline ? "Systems operational" : "Connection unavailable"}
      </p>
      {health?.service ? (
        <p className="mt-2 text-sm text-muted-foreground">{health.service}</p>
      ) : null}
    </div>
  );
}
