"use client";

import { useCallback, useState } from "react";
import { Plus, Trash2 } from "lucide-react";

import {
  ConversationArea,
  type Message,
} from "@/components/ai-workspace/copilot/conversation-area";
import { ReferencedDocuments } from "@/components/ai-workspace/copilot/referenced-documents";
import { SourcePanel } from "@/components/ai-workspace/copilot/source-panel";
import { PageHeader } from "@/components/common/page-header";
import { ChatTimeoutError, sendChatMessage } from "@/lib/api/chat";
import type { Citation } from "@/types/chat";

let messageCounter = 0;

function nextId(): string {
  messageCounter += 1;
  return `msg-${Date.now()}-${messageCounter}`;
}

export function CopilotPageContent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isWaiting, setIsWaiting] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [allSources, setAllSources] = useState<string[]>([]);
  const [lastCitations, setLastCitations] = useState<Citation[]>([]);

  const handleSubmit = useCallback(async () => {
    const question = draft.trim();
    if (!question || isWaiting) return;

    setDraft("");
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content: question },
    ]);
    setIsWaiting(true);

    try {
      const response = await sendChatMessage({
        question,
        conversation_id: conversationId,
      });

      setConversationId(response.conversation_id);
      setLastCitations(response.citations);
      setAllSources(response.sources);

      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: response.answer,
          citations: response.citations,
        },
      ]);
    } catch (err) {
      let message: string;
      if (err instanceof ChatTimeoutError) {
        message =
          "The request timed out. The AI service may be busy or unavailable — please try again.";
      } else if (
        err instanceof Error &&
        err.message === "INSUFFICIENT_CONTEXT"
      ) {
        message =
          "I could not find this information in the uploaded documents.";
      } else {
        message = "Sorry, a server error occurred. Please try again.";
      }
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: message,
        },
      ]);
    } finally {
      setIsWaiting(false);
    }
  }, [draft, isWaiting, conversationId]);

  function handleNewConversation() {
    setMessages([]);
    setConversationId(null);
    setAllSources([]);
    setLastCitations([]);
    setDraft("");
  }

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="AI Workspace"
        title="Copilot"
        description="Conversational interface for grounded industrial knowledge."
        action={
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleNewConversation}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-[var(--surface-secondary)] px-3 text-xs font-medium text-muted-foreground transition-industrial hover:border-[var(--accent-steel)]/25 hover:text-white"
            >
              <Plus className="size-3.5" strokeWidth={1.75} />
              New conversation
            </button>
            {conversationId && (
              <button
                type="button"
                onClick={async () => {
                  const { clearAllConversations } = await import(
                    "@/lib/api/chat"
                  );
                  await clearAllConversations();
                  handleNewConversation();
                }}
                className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-[var(--surface-secondary)] px-3 text-xs font-medium text-muted-foreground transition-industrial hover:border-[var(--danger)]/30 hover:text-[var(--danger)]"
              >
                <Trash2 className="size-3.5" strokeWidth={1.75} />
                Clear chat
              </button>
            )}
          </div>
        }
      />

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="flex flex-col gap-6 xl:col-span-8">
          <div className="min-h-[600px]">
            <ConversationArea
              messages={messages}
              isWaiting={isWaiting}
              draft={draft}
              onDraftChange={setDraft}
              onSubmit={handleSubmit}
            />
          </div>
        </div>

        <div className="flex flex-col gap-6 xl:col-span-4">
          <div className="max-h-[300px] overflow-y-auto">
            <ReferencedDocuments sources={allSources} />
          </div>
          <div className="flex-1 overflow-y-auto">
            <SourcePanel citations={lastCitations} />
          </div>
        </div>
      </div>
    </div>
  );
}
