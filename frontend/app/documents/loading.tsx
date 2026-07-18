export default function DocumentsLoading() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="size-8 animate-spin rounded-full border-2 border-[var(--accent-steel)] border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading documents...</p>
      </div>
    </div>
  );
}
