import { FutureNotice } from "@/components/ai-workspace/future-notice";
import { AgentCard } from "@/components/ai-workspace/agents/agent-card";
import { PageHeader } from "@/components/common/page-header";
import { AI_AGENTS } from "@/lib/ai-workspace/mock-data";

export function AiAgentsPageContent() {
  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="AI Workspace"
        title="AI Agents"
        description="Specialized LangGraph agents for maintenance, compliance, SOPs, search, root cause analysis, and lessons learned."
      />

      <FutureNotice
        description="Agent orchestration via LangGraph is planned for a future milestone."
      />

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {AI_AGENTS.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
      </div>
    </div>
  );
}
