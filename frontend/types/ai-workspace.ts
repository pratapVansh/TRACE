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

export type AgentStatus = "coming_soon" | "planned" | "active";

export interface AiAgent {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  status: AgentStatus;
  icon: LucideIcon;
}

export interface AgentCitation {
  chunk_id: string;
  document_name: string;
  page_number: number | null;
  chunk_content: string;
  score: number;
  similarity_score: number;
  highlighted_excerpt: string;
}

export interface GraphCitation {
  entity_name: string;
  relationship_type: string;
  related_entity: string;
  confidence: number;
}

export interface TimelineEntry {
  agent_id: string;
  agent_name: string;
  start_time: number;
  end_time: number;
  duration: number;
  confidence: number;
  tools_used: string[];
  status: string;
}

export interface ClassifiedStatement {
  text: string;
  classification: "FACT" | "HYPOTHESIS" | "UNKNOWN";
  evidence_refs: string[];
}

export interface EvidenceSummary {
  has_supporting_evidence: boolean;
  missing_evidence_statement: string;
  top_citation_count: number;
}

export interface AgentResult {
  answer: string;
  reasoning: string;
  citations: AgentCitation[];
  graph_citations: GraphCitation[];
  confidence: number;
  execution_time: number;
  tools_used: string[];
  agent_name: string;
  classified_statements?: ClassifiedStatement[];
  evidence_summary?: EvidenceSummary;
}

export interface MultiAgentResponse {
  answer: string;
  conversation_id?: string;
  agent_results: AgentResult[];
  citations: AgentCitation[];
  graph_citations: GraphCitation[];
  confidence: number;
  execution_time: number;
  execution_order: string[];
  timeline: TimelineEntry[];
  all_tools_used: string[];
  parallel_groups: string[][] | null;
}
