export function TypingIndicator() {
  return (
    <div className="flex items-center gap-2 px-5 py-3">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-[var(--accent-steel)]/25 bg-[var(--accent-steel)]/10 text-[var(--accent-steel-muted)]">
        <svg
          className="size-4"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.75}
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"
          />
        </svg>
      </div>
      <div className="flex items-center gap-1.5 rounded-xl border border-[var(--accent-steel)]/20 bg-[var(--surface)] px-4 py-3">
        <span className="size-1.5 animate-bounce rounded-full bg-[var(--accent-steel-muted)] [animation-delay:0ms]" />
        <span className="size-1.5 animate-bounce rounded-full bg-[var(--accent-steel-muted)] [animation-delay:150ms]" />
        <span className="size-1.5 animate-bounce rounded-full bg-[var(--accent-steel-muted)] [animation-delay:300ms]" />
      </div>
    </div>
  );
}
