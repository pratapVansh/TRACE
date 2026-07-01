import type { LucideIcon } from "lucide-react";

export type MessageRole = "user" | "assistant";

export interface CopilotMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  citationIds?: string[];
}

export interface ReferencedDocument {
  id: string;
  title: string;
  type: string;
  page?: string;
  relevance: number;
}

export interface SourceExcerpt {
  id: string;
  documentId: string;
  documentTitle: string;
  page: string;
  excerpt: string;
  highlighted?: string;
}

export interface SuggestedPrompt {
  id: string;
  label: string;
  prompt: string;
}

export interface GraphStat {
  label: string;
  value: string;
}

export interface GraphInfoItem {
  id: string;
  label: string;
  description: string;
}

export type AgentStatus = "coming_soon" | "planned";

export interface AiAgent {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  status: AgentStatus;
  icon: LucideIcon;
}
