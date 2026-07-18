export default function CopilotLoading() {
  return (
    <div className="flex min-h-full items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3">
        <div className="size-8 animate-spin rounded-full border-2 border-[var(--accent-steel)] border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading assistant...</p>
      </div>
    </div>
  );
}
