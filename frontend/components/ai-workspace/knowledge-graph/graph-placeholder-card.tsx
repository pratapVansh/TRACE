export function GraphPlaceholderCard() {
  return (
    <div className="industrial-card relative aspect-[16/10] min-h-[360px] overflow-hidden p-6">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(91,127,168,0.08),transparent_70%)]" />

      <div className="relative mb-4">
        <p className="section-label">Visualization</p>
        <h3 className="text-lg font-semibold text-foreground">Knowledge graph</h3>
      </div>

      <div className="absolute inset-0 flex items-center justify-center bg-[var(--surface)]/60 backdrop-blur-[1px]">
        <div className="rounded-xl border border-border bg-[var(--surface)]/95 px-6 py-4 text-center shadow-lg">
          <p className="text-sm font-medium text-foreground">Knowledge graph not generated.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Upload documents and process assets to generate the knowledge graph.
          </p>
        </div>
      </div>
    </div>
  );
}
