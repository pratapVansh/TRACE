import type { Metadata } from "next";
import { AgentChatContent } from "@/components/ai-workspace/agents/agent-chat-content";

export const metadata: Metadata = {
  title: "Multi-Agent System",
  description:
    "Execute multi-agent workflows with automatic routing, chaining, parallel execution, and fallback.",
};

export default function AgentChatPage() {
  return <AgentChatContent />;
}
