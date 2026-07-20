import { apiClient } from "./client";
import type {
  AgentResult,
  MultiAgentResponse,
} from "@/types/ai-workspace";
import type { Citation } from "@/types/chat";

export interface AgentExecuteRequest {
  question: string;
  conversation_id?: string | null;
  agent_id?: string | null;
}

export interface MultiAgentRequest {
  question: string;
  conversation_id?: string | null;
  agent_ids?: string[] | null;
  mode?: string;
}

export async function executeAgent(
  params: AgentExecuteRequest,
): Promise<AgentResult> {
  const { data } = await apiClient.post<AgentResult>(
    "/api/agents/execute",
    params,
  );
  return data;
}

import { authStorage } from "@/lib/auth/storage";

export async function executeMultiAgent(
  params: MultiAgentRequest,
): Promise<MultiAgentResponse> {
  const { data } = await apiClient.post<MultiAgentResponse>(
    "/api/agents/execute-multi",
    params,
  );
  return data;
}

export async function streamMultiAgent(
  params: MultiAgentRequest,
  onEvent: (event: string, data: any) => void,
  signal?: AbortSignal
): Promise<void> {
  const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const token = authStorage.getAccessToken();
  
  const response = await fetch(`${API_URL}/api/agents/stream-multi`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(params),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Stream failed with status ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No reader available");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || "";
    
    for (const part of parts) {
      if (!part.trim()) continue;
      
      let eventType = "message";
      let data = "";
      
      const lines = part.split('\n');
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          data = line.slice(6); // do not trim as tokens might have spaces
        }
      }
      
      if (data) {
        try {
          const parsed = JSON.parse(data);
          onEvent(eventType, parsed);
        } catch (e) {
          onEvent(eventType, data);
        }
      }
    }
  }
}
