import type { Metadata } from "next";

import { AgentChatContent } from "@/components/ai-workspace/agents/agent-chat-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export const metadata: Metadata = {
  title: "Multi-Agent System",
  description:
    "Execute multi-agent workflows with automatic routing, chaining, parallel execution, and fallback.",
};

export default function AgentChatPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.AI_AGENTS}>
      <AgentChatContent />
    </ProtectedPage>
  );
}
