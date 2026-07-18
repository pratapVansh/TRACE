"use client";

import { useEffect } from "react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Dashboard error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h2 className="text-lg font-semibold text-white">
          Dashboard error
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Failed to load dashboard data.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-4 rounded-xl bg-[var(--accent-steel)] px-4 py-2 text-sm font-medium text-white transition-industrial hover:bg-[var(--accent-steel)]/80"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
