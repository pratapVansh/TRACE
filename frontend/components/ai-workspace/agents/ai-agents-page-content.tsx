import Link from "next/link";
import { Bot, ExternalLink } from "lucide-react";

import { AgentCard } from "@/components/ai-workspace/agents/agent-card";
import { PageHeader } from "@/components/common/page-header";
import { AI_AGENTS } from "@/lib/ai-workspace/mock-data";

export function AiAgentsPageContent() {

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="AI Workspace"
        title="AI Agents"
        description="Specialized agents for maintenance, compliance, asset intelligence, root cause analysis, and reporting."
        action={
          <Link
            href="/ai-agents/chat"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[var(--accent-steel)]/30 bg-[var(--accent-steel)]/10 px-4 text-xs font-medium text-[var(--accent-steel-muted)] transition-industrial hover:bg-[var(--accent-steel)]/20 hover:text-white"
          >
            <Bot className="size-3.5" strokeWidth={1.75} />
            Multi-Agent Chat
            <ExternalLink className="size-3" strokeWidth={1.75} />
          </Link>
        }
      />

      <div className="rounded-xl border border-[var(--accent-steel)]/10 bg-[var(--accent-steel)]/5 px-5 py-4">
        <p className="text-xs leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">7 agents active.</span>{" "}
          Ask a question and the system automatically routes it to the
          appropriate specialist agent(s). Supports chaining, parallel
          execution, and fallback.{" "}
          <Link
            href="/ai-agents/chat"
            className="text-[var(--accent-steel-muted)] underline hover:text-white transition-industrial"
          >
            Try the multi-agent chat
          </Link>
          .
        </p>
      </div>

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {AI_AGENTS.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
      </div>
    </div>
  );
}
