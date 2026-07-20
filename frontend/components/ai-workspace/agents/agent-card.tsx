import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import type { AiAgent } from "@/types/ai-workspace";
import { cn } from "@/lib/utils";

type AgentCardProps = {
  agent: AiAgent;
};

export function AgentCard({ agent }: AgentCardProps) {
  const Icon = agent.icon;
  const isActive = agent.status === "active";

  return (
    <article className="industrial-card flex h-full flex-col p-6 transition-industrial hover:border-[var(--accent-steel)]/20">
      <div className="flex items-start justify-between gap-3">
        <div className="flex size-12 items-center justify-center rounded-xl border border-border bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)]">
          <Icon className="size-5" strokeWidth={1.75} />
        </div>
        <Badge variant={isActive ? "default" : "warning"}>
          {isActive ? "Active" : "Coming soon"}
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

      {isActive ? (
        <Link
          href="/ai-agents/chat"
          className={cn(
            "mt-5 flex h-10 w-full items-center justify-center rounded-xl text-sm font-medium transition-industrial",
            "border border-[var(--accent-steel)]/30 bg-[var(--accent-steel)]/10 text-[var(--accent-steel-muted)]",
            "hover:bg-[var(--accent-steel)]/20 hover:text-white",
          )}
        >
          Launch agent
        </Link>
      ) : (
        <button
          type="button"
          disabled
          className="mt-5 h-10 w-full rounded-xl border border-border bg-[var(--surface-secondary)] text-sm font-medium text-muted-foreground"
        >
          Launch agent
        </button>
      )}
    </article>
  );
}
