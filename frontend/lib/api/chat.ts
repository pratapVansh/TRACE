import { authStorage } from "@/lib/auth/storage";
import { apiClient } from "./client";
import type {
  ArchiveConversationResponse,
  ArchiveListResponse,
  ChatRequest,
  ChatResponse,
  ConversationMessagesResponse,
  ConversationsListResponse,
  SaveSnapshotRequest,
  SnapshotListResponse,
  SnapshotResponse,
  SseCallbacks,
} from "@/types/chat";

const CHAT_TIMEOUT_MS = 30_000;

// ── Session cookie (survives browser restart) ──────────────────────

const SESSION_COOKIE = "trace_sid";

function getSessionId(): string {
  const match = document.cookie.match(new RegExp(`(?:^|; )${SESSION_COOKIE}=([^;]*)`));
  if (match) return match[1];
  return createSessionId();
}

function createSessionId(): string {
  const id = crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  setSessionId(id);
  return id;
}

function setSessionId(id: string): void {
  document.cookie = `${SESSION_COOKIE}=${id}; path=/; max-age=31536000; SameSite=Lax`;
}

export function ensureSessionId(): string {
  const existing = getSessionId();
  if (existing) return existing;
  return createSessionId();
}

export function rotateSessionId(): string {
  return createSessionId();
}

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
      session_id: params.session_id ?? ensureSessionId(),
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

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STREAM_READ_TIMEOUT_MS = 60_000;

async function readWithTimeout(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  timeoutMs: number,
): Promise<ReadableStreamReadResult<Uint8Array>> {
  const timeoutPromise = new Promise<never>((_, reject) => {
    setTimeout(() => reject(new Error("Stream read timeout")), timeoutMs);
  });
  return Promise.race([reader.read(), timeoutPromise]);
}

export async function streamChatMessage(
  params: ChatRequest,
  callbacks: SseCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const accessToken = authStorage.getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${API_URL}/api/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      question: params.question,
      conversation_id: params.conversation_id ?? null,
      session_id: params.session_id ?? ensureSessionId(),
      top_k: params.top_k ?? 5,
      similarity_threshold: params.similarity_threshold ?? 0.0,
    }),
    signal,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`Chat stream failed (${response.status}): ${body}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await readWithTimeout(reader, STREAM_READ_TIMEOUT_MS);
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let eventType = "";
      let dataStr = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataStr = line.slice(6).trim();
        } else if (line === "") {
          if (eventType && dataStr) {
            try {
              const data = JSON.parse(dataStr);
              switch (eventType) {
                case "meta":
                  callbacks.onMeta?.(data);
                  break;
                case "citations":
                  callbacks.onCitations?.(data);
                  break;
                case "token":
                  callbacks.onToken?.(data.token);
                  break;
                case "done":
                  callbacks.onDone?.(data);
                  break;
                case "error":
                  callbacks.onError?.(data.message);
                  break;
              }
            } catch {
              // skip malformed events
            }
          }
          eventType = "";
          dataStr = "";
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function listConversations(
  params?: { skip?: number; limit?: number; search?: string },
): Promise<ConversationsListResponse> {
  const { data } = await apiClient.get<ConversationsListResponse>(
    "/api/chat/conversations",
    { params },
  );
  return data;
}

export async function renameConversation(
  conversationId: string,
  title: string,
): Promise<{ id: string; title: string }> {
  const { data } = await apiClient.patch<{ id: string; title: string }>(
    `/api/chat/conversations/${conversationId}`,
    { title },
  );
  return data;
}

/** Fetch the conversation associated with a persistent session_id. */
export async function fetchSessionConversation(
  sessionId: string,
): Promise<ConversationMessagesResponse | null> {
  try {
    const { data } = await apiClient.get<ConversationMessagesResponse>(
      `/api/chat/session/${sessionId}`,
    );
    return data;
  } catch {
    return null;
  }
}

export async function fetchMessages(
  conversationId: string,
): Promise<ConversationMessagesResponse> {
  const { data } = await apiClient.get<ConversationMessagesResponse>(
    `/api/chat/conversations/${conversationId}/messages`,
  );
  return data;
}

export async function addMessage(
  conversationId: string,
  payload: {
    role: "user" | "assistant";
    content: string;
    citations?: Array<Record<string, unknown>>;
    tool_outputs?: Array<Record<string, unknown>>;
  },
): Promise<{
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  citations: Array<Record<string, unknown>> | null;
  tool_outputs: Array<Record<string, unknown>> | null;
  created_at: number;
}> {
  const { data } = await apiClient.post("/api/chat/messages", {
    conversation_id: conversationId,
    ...payload,
  });
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

// ── Archive / Restore ─────────────────────────────────────────

export async function archiveConversation(
  conversationId: string,
): Promise<ArchiveConversationResponse> {
  const { data } = await apiClient.patch<ArchiveConversationResponse>(
    `/api/chat/conversations/${conversationId}/archive`,
  );
  return data;
}

export async function restoreConversation(
  conversationId: string,
): Promise<ArchiveConversationResponse> {
  const { data } = await apiClient.patch<ArchiveConversationResponse>(
    `/api/chat/conversations/${conversationId}/restore`,
  );
  return data;
}

export async function listArchivedConversations(
  params?: { skip?: number; limit?: number },
): Promise<ArchiveListResponse> {
  const { data } = await apiClient.get<ArchiveListResponse>(
    "/api/chat/conversations/archived",
    { params },
  );
  return data;
}

// ── Snapshots ─────────────────────────────────────────────────

export async function saveConversationSnapshot(
  conversationId: string,
  payload: SaveSnapshotRequest,
): Promise<SnapshotResponse> {
  const { data } = await apiClient.post<SnapshotResponse>(
    `/api/chat/conversations/${conversationId}/snapshots`,
    payload,
  );
  return data;
}

export async function getConversationSnapshots(
  conversationId: string,
): Promise<SnapshotListResponse> {
  const { data } = await apiClient.get<SnapshotListResponse>(
    `/api/chat/conversations/${conversationId}/snapshots`,
  );
  return data;
}

export async function getConversationSnapshot(
  conversationId: string,
  turnIndex: number,
): Promise<SnapshotResponse> {
  const { data } = await apiClient.get<SnapshotResponse>(
    `/api/chat/conversations/${conversationId}/snapshots/${turnIndex}`,
  );
  return data;
}
