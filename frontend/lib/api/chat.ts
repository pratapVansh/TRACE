import { apiClient } from "./client";
import type {
  ChatRequest,
  ChatResponse,
  ConversationsListResponse,
} from "@/types/chat";

const CHAT_TIMEOUT_MS = 30_000;

export class ChatTimeoutError extends Error {
  constructor() {
    super("CHAT_TIMEOUT");
    this.name = "ChatTimeoutError";
  }
}

export async function sendChatMessage(
  params: ChatRequest,
): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>(
    "/api/chat",
    {
      question: params.question,
      conversation_id: params.conversation_id ?? null,
      top_k: params.top_k ?? 5,
      similarity_threshold: params.similarity_threshold ?? 0.0,
    },
    {
      timeout: CHAT_TIMEOUT_MS,
      signal: AbortSignal.timeout(CHAT_TIMEOUT_MS),
    },
  );
  return data;
}

export async function listConversations(): Promise<ConversationsListResponse> {
  const { data } = await apiClient.get<ConversationsListResponse>(
    "/api/chat/conversations",
  );
  return data;
}

export async function clearConversation(
  conversationId: string,
): Promise<void> {
  await apiClient.delete(`/api/chat/conversations/${conversationId}`);
}

export async function clearAllConversations(): Promise<void> {
  await apiClient.delete("/api/chat/conversations");
}
