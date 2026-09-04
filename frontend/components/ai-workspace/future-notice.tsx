import { Sparkles } from "lucide-react";

type FutureNoticeProps = {
  title?: string;
  description?: string;
};

export function FutureNotice({
  title = "Future implementation",
  description = "This capability will be powered by LangGraph agents, RAG retrieval, and the Neo4j knowledge graph in an upcoming milestone. The UI shown here is a design preview only.",
}: FutureNoticeProps) {
  return (
    <div className="flex items-start gap-4 rounded-xl border border-[var(--accent-steel)]/20 bg-[var(--accent-steel)]/5 p-5">
      <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-[var(--accent-steel)]/25 bg-[var(--surface)] text-[var(--accent-steel-muted)]">
        <Sparkles className="size-4.5" strokeWidth={1.75} />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
