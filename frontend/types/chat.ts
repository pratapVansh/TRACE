export interface Citation {
  /** Null when the retriever could not identify the chunk — not "". */
  chunk_id: string | null;
  /** Null when the passage could not be traced back to a document. */
  document_id: string | null;
  document_name: string;
  page_number: number | null;
  chunk_content: string;
  score: number;
  similarity_score: number;
  highlighted_excerpt: string;
}

export type Classification = "FACT" | "HYPOTHESIS" | "UNKNOWN";

export interface ClassifiedStatement {
  text: string;
  classification: Classification;
  /** Document names of the passages whose wording this statement overlaps. */
  evidence_refs: string[];
}

export interface EvidenceSummary {
  fact_count: number;
  hypothesis_count: number;
  unknown_count: number;
}

export interface EvidencePayload {
  classified_statements: ClassifiedStatement[];
  evidence: EvidenceSummary;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  sources: string[];
  confidence: number;
  processing_time: number;
  conversation_id: string;
  classified_statements: ClassifiedStatement[];
  evidence: EvidenceSummary;
}

export interface ChatRequest {
  question: string;
  conversation_id?: string | null;
  session_id?: string | null;
  top_k?: number;
  similarity_threshold?: number;
}

export interface ConversationItem {
  id: string;
  title: string | null;
  message_count: number;
  created_at: number;
  updated_at: number;
  status?: string;
}

export interface ConversationsListResponse {
  conversations: ConversationItem[];
  total: number;
}

export interface MessageItem {
  id: string;
  role: string;
  content: string;
  citations: Citation[] | null;
  tool_outputs?: Record<string, unknown>[] | null;
  sources?: string[];
  created_at: number;
}

export interface ConversationMessagesResponse {
  messages: MessageItem[];
  conversation_id: string;
  title: string | null;
}

// ── Archive ────────────────────────────────────────────────────

export interface ArchiveConversationResponse {
  id: string;
  status: string;
}

export interface ArchiveListResponse {
  conversations: ConversationItem[];
  total: number;
}

// ── Snapshots ──────────────────────────────────────────────────

export interface SnapshotData {
  working_memory?: Record<string, unknown> | null;
  tool_outputs?: Record<string, unknown>[] | null;
  agent_results?: Record<string, unknown>[] | null;
  timeline?: Record<string, unknown>[] | null;
}

export interface SaveSnapshotRequest {
  turn_index: number;
  role: string;
  data: SnapshotData;
}

export interface SnapshotResponse {
  id: string;
  conversation_id: string;
  turn_index: number;
  role: string;
  working_memory: Record<string, unknown> | null;
  tool_outputs: Record<string, unknown>[] | null;
  agent_results: Record<string, unknown>[] | null;
  timeline: Record<string, unknown>[] | null;
  created_at: number;
}

export interface SnapshotListResponse {
  snapshots: SnapshotResponse[];
}

export interface SseCallbacks {
  onMeta?: (data: { conversation_id: string }) => void;
  onCitations?: (data: { citations: Citation[]; sources: string[] }) => void;
  onToken?: (token: string) => void;
  /** Arrives immediately before `done`, once the full answer is known. */
  onEvidence?: (data: EvidencePayload) => void;
  onDone?: (data: { confidence: number }) => void;
  onError?: (message: string) => void;
}
