export interface Citation {
  document_name: string;
  page_number: number | null;
  chunk_content: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  sources: string[];
  confidence: number;
  processing_time: number;
  conversation_id: string;
}

export interface ChatRequest {
  question: string;
  conversation_id?: string | null;
  top_k?: number;
  similarity_threshold?: number;
}

export interface ConversationItem {
  id: string;
  message_count: number;
  created_at: number;
  updated_at: number;
}

export interface ConversationsListResponse {
  conversations: ConversationItem[];
  total: number;
}
