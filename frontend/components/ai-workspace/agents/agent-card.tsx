import { Badge } from "@/components/ui/badge";
import type { AiAgent } from "@/types/ai-workspace";

type AgentCardProps = {
  agent: AiAgent;
};

export function AgentCard({ agent }: AgentCardProps) {
  const Icon = agent.icon;
  const isComingSoon = agent.status === "coming_soon";

  return (
    <article className="industrial-card flex h-full flex-col p-6 transition-industrial hover:border-[var(--accent-steel)]/20">
      <div className="flex items-start justify-between gap-3">
        <div className="flex size-12 items-center justify-center rounded-xl border border-border bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)]">
          <Icon className="size-5" strokeWidth={1.75} />
        </div>
        <Badge variant={isComingSoon ? "warning" : "secondary"}>
          {isComingSoon ? "Coming soon" : "Planned"}
        </Badge>
      </div>

      <h3 className="mt-5 text-lg font-semibold text-white">{agent.name}</h3>
      <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
        {agent.description}
      </p>

      <ul className="mt-5 space-y-2 border-t border-border pt-5">
        {agent.capabilities.map((capability) => (
          <li
            key={capability}
            className="flex items-center gap-2 text-xs text-muted-foreground"
          >
            <span className="size-1.5 shrink-0 rounded-full bg-[var(--accent-steel-muted)]" />
            {capability}
          </li>
        ))}
      </ul>

      <button
        type="button"
        disabled
        className="mt-5 h-10 w-full rounded-xl border border-border bg-[var(--surface-secondary)] text-sm font-medium text-muted-foreground"
      >
        Launch agent
      </button>
    </article>
  );
}
