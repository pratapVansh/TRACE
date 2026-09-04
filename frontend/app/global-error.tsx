"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="flex min-h-screen items-center justify-center bg-background p-8">
        <div className="max-w-md text-center">
          <h2 className="text-xl font-semibold text-foreground">
            Critical application error
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            A critical error occurred. Please reload the application.
          </p>
          <button
            type="button"
            onClick={reset}
            className="mt-6 rounded-xl bg-[var(--accent-steel)] px-5 py-2.5 text-sm font-medium text-white transition-industrial hover:bg-[var(--accent-steel)]/80"
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
