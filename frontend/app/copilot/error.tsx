"use client";

import { useEffect } from "react";

export default function CopilotError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Copilot page error:", error);
  }, [error]);

  return (
    <div className="flex min-h-full items-center justify-center bg-background p-8">
      <div className="max-w-md text-center">
        <div className="mx-auto mb-6 flex size-16 items-center justify-center rounded-2xl border border-[var(--danger)]/20 bg-[var(--danger)]/10">
          <svg
            className="size-8 text-[var(--danger)]"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-white">
          Copilot encountered an issue
        </h2>
        <p className="mt-3 text-sm text-muted-foreground">
          The assistant experienced an error. Your conversation is still saved.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <button
            type="button"
            onClick={reset}
            className="rounded-xl border border-border bg-[var(--surface-secondary)] px-5 py-2.5 text-sm font-medium text-white transition-industrial hover:border-[var(--accent-steel)]/25"
          >
            Try again
          </button>
          <a
            href="/copilot"
            className="rounded-xl bg-[var(--accent-steel)] px-5 py-2.5 text-sm font-medium text-white transition-industrial hover:bg-[var(--accent-steel)]/80"
          >
            New conversation
          </a>
        </div>
      </div>
    </div>
  );
}
