export interface Citation {
  chunk_id: string;
  document_name: string;
  page_number: number | null;
  chunk_content: string;
  score: number;
  similarity_score: number;
  highlighted_excerpt: string;
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
  title: string | null;
  message_count: number;
  created_at: number;
  updated_at: number;
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
  created_at: number;
}

export interface ConversationMessagesResponse {
  messages: MessageItem[];
  conversation_id: string;
  title: string | null;
}

export interface SseCallbacks {
  onMeta?: (data: { conversation_id: string }) => void;
  onCitations?: (data: { citations: Citation[]; sources: string[] }) => void;
  onToken?: (token: string) => void;
  onDone?: (data: { confidence: number }) => void;
  onError?: (message: string) => void;
}
