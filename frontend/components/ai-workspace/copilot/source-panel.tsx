import type { SourceExcerpt } from "@/types/ai-workspace";

type SourcePanelProps = {
  sources: SourceExcerpt[];
  activeDocumentId?: string;
};

export function SourcePanel({ sources, activeDocumentId }: SourcePanelProps) {
  const filtered = activeDocumentId
    ? sources.filter((s) => s.documentId === activeDocumentId)
    : sources;

  return (
    <div className="industrial-card flex h-full flex-col p-5">
      <p className="section-label">Provenance</p>
      <h3 className="mt-1 text-base font-semibold text-white">Source panel</h3>
      <p className="mt-2 text-xs text-muted-foreground">
        Grounded excerpts from indexed technical records.
      </p>

      <ul className="mt-4 flex-1 space-y-3 overflow-y-auto">
        {filtered.map((source) => (
          <li
            key={source.id}
            className="rounded-xl border border-border bg-[var(--surface-secondary)] p-4"
          >
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-medium text-white">{source.documentTitle}</p>
              <span className="text-[11px] text-[var(--accent-steel-muted)]">{source.page}</span>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {source.highlighted ? (
                <>
                  {source.excerpt.split(source.highlighted)[0]}
                  <mark className="rounded bg-[var(--accent-steel)]/20 px-0.5 text-[var(--accent-steel-muted)]">
                    {source.highlighted}
                  </mark>
                  {source.excerpt.split(source.highlighted)[1]}
                </>
              ) : (
                source.excerpt
              )}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
