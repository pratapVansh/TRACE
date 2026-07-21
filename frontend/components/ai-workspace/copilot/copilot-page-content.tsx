"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Menu, Plus, Trash2, X } from "lucide-react";

import {
  ConversationArea,
  type Message,
} from "@/components/ai-workspace/copilot/conversation-area";
import { ConversationSidebar } from "@/components/ai-workspace/copilot/conversation-sidebar";
import { SourcePreviewModal } from "@/components/ai-workspace/copilot/source-preview-modal";
import { PageHeader } from "@/components/common/page-header";
import {
  ChatTimeoutError,
  archiveConversation,
  clearConversation,
  ensureSessionId,
  fetchMessages,
  fetchSessionConversation,
  listArchivedConversations,
  listConversations,
  renameConversation,
  restoreConversation,
  rotateSessionId,
  saveConversationSnapshot,
  streamChatMessage,
} from "@/lib/api/chat";
import type { Citation, ConversationItem } from "@/types/chat";

const STORAGE_KEY = "lastConversationId";

function getStoredConversationId(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

function setStoredConversationId(id: string | null) {
  if (id) {
    localStorage.setItem(STORAGE_KEY, id);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function getUrlConversationId(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return params.get("conv");
}

function setUrlConversationId(id: string | null) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (id) {
    url.searchParams.set("conv", id);
  } else {
    url.searchParams.delete("conv");
  }
  window.history.replaceState(null, "", url.toString());
}

let messageCounter = 0;

function nextId(): string {
  messageCounter += 1;
  return `msg-${Date.now()}-${messageCounter}`;
}

function restoreConversationState(
  msgData: import("@/types/chat").ConversationMessagesResponse,
  setters: {
    setMessages: (msgs: import("@/components/ai-workspace/copilot/conversation-area").Message[]) => void;
    setAllSources: (sources: string[]) => void;
    setLastCitations: (citations: import("@/types/chat").Citation[]) => void;
    turnIndexRef: { current: number };
  },
) {
  const messages = msgData.messages.map((m) => ({
    id: m.id,
    role: m.role as "user" | "assistant",
    content: m.content,
    citations: m.citations ?? undefined,
    sources: m.sources ?? undefined,
  }));

  setters.setMessages(messages);

  const allDocNames = new Set<string>();
  let lastAssistantCitations: import("@/types/chat").Citation[] = [];
  let assistantCount = 0;

  for (const m of msgData.messages) {
    if (m.role === "assistant") {
      assistantCount += 1;
      if (m.citations && m.citations.length > 0) {
        lastAssistantCitations = m.citations as import("@/types/chat").Citation[];
        for (const c of m.citations) {
          if (c.document_name) allDocNames.add(c.document_name);
        }
      }
    }
  }

  setters.setAllSources(Array.from(allDocNames));
  setters.setLastCitations(lastAssistantCitations);
  setters.turnIndexRef.current = assistantCount;
}

export function CopilotPageContent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isWaiting, setIsWaiting] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [allSources, setAllSources] = useState<string[]>([]);
  const [lastCitations, setLastCitations] = useState<Citation[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [archivedConversations, setArchivedConversations] = useState<ConversationItem[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [restoreNotice, setRestoreNotice] = useState<"not_found" | "incomplete" | null>(null);
  const turnIndexRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const hydratedRef = useRef(false);

  // Persist conversation ID to localStorage + URL whenever it changes,
  // but skip the initial hydration render to avoid clobbering saved IDs.
  useEffect(() => {
    if (!hydratedRef.current) return;
    setStoredConversationId(conversationId);
    setUrlConversationId(conversationId);
  }, [conversationId]);
  // Load conversation list on mount, restore by session_id or last saved
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        // Priority 1: restore via persistent session cookie
        const sessionId = ensureSessionId();
        const sessionConv = await fetchSessionConversation(sessionId);
        if (!cancelled && sessionConv && sessionConv.messages.length > 0) {
          setConversationId(sessionConv.conversation_id);
          restoreConversationState(sessionConv, {
            setMessages, setAllSources, setLastCitations, turnIndexRef,
          });
          const lastMsg = sessionConv.messages[sessionConv.messages.length - 1];
          const endsAbruptly = lastMsg.content.endsWith("...") || lastMsg.content.endsWith("…");
          if (lastMsg.role === "assistant" && endsAbruptly) {
            setRestoreNotice("incomplete");
          }
          // still fetch the conversation list for the sidebar
          listConversations().then((d) => {
            if (!cancelled) setConversations(d.conversations);
          }).catch(() => {});
          return;
        }

        // Priority 2: restore via saved conversationId (legacy)
        const data = await listConversations();
        if (cancelled) return;
        setConversations(data.conversations);

        const urlId = getUrlConversationId();
        const storedId = getStoredConversationId();
        const savedId = urlId ?? storedId;

        const target = savedId
          ? data.conversations.find((c) => c.id === savedId)
          : null;

        if (target) {
          setConversationId(target.id);
          const msgData = await fetchMessages(target.id);
          if (cancelled) return;
          if (msgData.messages.length > 0) {
            restoreConversationState(msgData, {
              setMessages,
              setAllSources,
              setLastCitations,
              turnIndexRef,
            });
            const lastMsg = msgData.messages[msgData.messages.length - 1];
            const endsAbruptly = lastMsg.content.endsWith("...") || lastMsg.content.endsWith("…");
            if (lastMsg.role === "assistant" && endsAbruptly) {
              setRestoreNotice("incomplete");
            }
          }
        } else if (data.conversations.length > 0) {
          const latest = data.conversations[0];
          setConversationId(latest.id);
          const msgData = await fetchMessages(latest.id);
          if (cancelled) return;
          restoreConversationState(msgData, {
            setMessages,
            setAllSources,
            setLastCitations,
            turnIndexRef,
          });
        } else if (savedId) {
          setRestoreNotice("not_found");
        }
      } catch {
        // if loading fails, start fresh
      } finally {
        if (!cancelled) {
          setLoadingConversations(false);
          hydratedRef.current = true;
        }
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  const handleSubmit = useCallback(async () => {
    const question = draft.trim();
    if (!question || isWaiting) return;
    if (messages.length > 0) {
      const last = messages[messages.length - 1];
      if (last.role === "user" && last.content === question) return;
    }

    setDraft("");
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content: question },
    ]);
    setIsWaiting(true);

    const assistantId = nextId();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setStreamingMessageId(assistantId);

    const controller = new AbortController();
    abortRef.current = controller;

    let accumulatedCitations: Citation[] = [];
    let accumulatedSources: string[] = [];

    try {
      await streamChatMessage(
        { question, conversation_id: conversationId },
        {
          onMeta(data) {
            setConversationId(data.conversation_id);
          },
          onCitations(data) {
            accumulatedCitations = data.citations;
            accumulatedSources = data.sources;
            setLastCitations(data.citations);
            setAllSources(data.sources);
          },
          onToken(token) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, content: msg.content + token }
                  : msg,
              ),
            );
          },
          onDone(data) {
            const citations = accumulatedCitations;
            const sources = accumulatedSources;
            setMessages((prev) => {
              const updated = prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, citations, sources }
                  : msg,
              );
              return updated;
            });
            setStreamingMessageId(null);
            // Save snapshot for this turn
            const currentConvId = conversationId ?? (data as any).conversation_id ?? "";
            if (currentConvId) {
              turnIndexRef.current += 1;
              saveConversationSnapshot(currentConvId, {
                turn_index: turnIndexRef.current,
                role: "assistant",
                data: {
                  tool_outputs: null,
                  timeline: null,
                  working_memory: null,
                  agent_results: null,
                },
              }).catch(() => {});
            }
            // Refresh conversation list to update message_count
            listConversations().then((convData) => {
              setConversations(convData.conversations);
            }).catch(() => {});
          },
          onError(message) {
            setStreamingMessageId(null);
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, content: `Error: ${message}` }
                  : msg,
              ),
            );
          },
        },
        controller.signal,
      );
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      let message: string;
      if (err instanceof ChatTimeoutError) {
        message =
          "The request timed out. The AI service may be busy or unavailable — please try again.";
      } else {
        message = "Sorry, a server error occurred. Please try again.";
      }
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? { ...msg, content: message }
            : msg,
        ),
      );
    } finally {
      setIsWaiting(false);
      abortRef.current = null;
    }
  }, [draft, isWaiting, conversationId]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages((prev) =>
      prev.map((msg) =>
        msg.role === "assistant" && msg.content === ""
          ? { ...msg, content: "Response cancelled." }
          : msg,
      ),
    );
    setIsWaiting(false);
  }, []);

  async function handleDeleteConversation(convId: string) {
    try {
      setDeleteConfirmId(null);
      await clearConversation(convId);
      if (convId === conversationId) {
        setMessages([]);
        setConversationId(null);
        setAllSources([]);
        setLastCitations([]);
      }
      const data = await listConversations();
      setConversations(data.conversations);
      if (data.conversations.length > 0 && convId === conversationId) {
        const latest = data.conversations[0];
        setConversationId(latest.id);
        const msgData = await fetchMessages(latest.id);
        restoreConversationState(msgData, {
          setMessages,
          setAllSources,
          setLastCitations,
          turnIndexRef,
        });
      }
    } catch {
      // silently fail
    }
  }

  async function handleSearchConversations(query: string) {
    setSearchQuery(query);
    try {
      const data = await listConversations({ search: query || undefined });
      setConversations(data.conversations);
    } catch {
      // silently fail
    }
  }

  async function handleArchiveConversation(convId: string) {
    try {
      await archiveConversation(convId);
      const [activeData, archivedData] = await Promise.all([
        listConversations(),
        listArchivedConversations(),
      ]);
      setConversations(activeData.conversations);
      setArchivedConversations(archivedData.conversations);
      if (convId === conversationId) {
        handleNewConversation();
      }
    } catch {
      // silently fail
    }
  }

  async function loadArchivedConversations() {
    try {
      const data = await listArchivedConversations();
      setArchivedConversations(data.conversations);
      setShowArchived(true);
    } catch {
      // silently fail
    }
  }

  function handleShowArchived() {
    loadArchivedConversations();
  }

  async function handleRenameConversation(convId: string, title: string) {
    try {
      await renameConversation(convId, title);
      setRenameId(null);
      setRenameValue("");
      const data = await listConversations({ search: searchQuery || undefined });
      setConversations(data.conversations);
    } catch {
      // silently fail
    }
  }

  function handleNewConversation() {
    handleCancel();
    setMessages([]);
    setConversationId(null);
    setAllSources([]);
    setLastCitations([]);
    setDraft("");
    setStoredConversationId(null);
    setUrlConversationId(null);
    setRestoreNotice(null);
    // Rotate session_id so the next request creates a fresh conversation
    rotateSessionId();
  }

  async function handleSelectConversation(convId: string) {
    if (convId === conversationId || isWaiting) return;
    handleCancel();
    setConversationId(convId);
    setRestoreNotice(null);
    try {
      const msgData = await fetchMessages(convId);
      restoreConversationState(msgData, {
        setMessages,
        setAllSources,
        setLastCitations,
        turnIndexRef,
      });
    } catch {
      setMessages([]);
      setAllSources([]);
      setLastCitations([]);
      turnIndexRef.current = 0;
    }
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
            {conversationId && deleteConfirmId === null && (
              <button
                type="button"
                onClick={() => setDeleteConfirmId("__all__")}
                className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-[var(--surface-secondary)] px-3 text-xs font-medium text-muted-foreground transition-industrial hover:border-[var(--danger)]/30 hover:text-[var(--danger)]"
              >
                <Trash2 className="size-3.5" strokeWidth={1.75} />
                Clear chat
              </button>
            )}
            {deleteConfirmId === "__all__" && (
              <div className="flex items-center gap-2 rounded-lg border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-3 py-1.5">
                <span className="text-xs text-[var(--danger)]">Delete all conversations?</span>
                <button
                  type="button"
                  onClick={async () => {
                    const { clearAllConversations } = await import("@/lib/api/chat");
                    await clearAllConversations();
                    setDeleteConfirmId(null);
                    handleNewConversation();
                  }}
                  className="flex size-5 items-center justify-center rounded text-[var(--danger)] hover:text-red-300"
                >
                  <svg className="size-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                </button>
                <button
                  type="button"
                  onClick={() => setDeleteConfirmId(null)}
                  className="flex size-5 items-center justify-center rounded text-muted-foreground hover:text-white"
                >
                  <svg className="size-3.5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
            )}
          </div>
        }
      />

      {/* Mobile sidebar toggle */}
      <div className="flex xl:hidden items-center gap-2">
        <button
          type="button"
          onClick={() => setMobileSidebarOpen(true)}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-[var(--surface-secondary)] px-3 text-xs font-medium text-muted-foreground transition-industrial hover:border-[var(--accent-steel)]/25 hover:text-white"
        >
          <Menu className="size-3.5" strokeWidth={1.75} />
          Conversations
        </button>
      </div>

      {/* Mobile sidebar overlay */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 xl:hidden">
          <div
            className="fixed inset-0 bg-black/50"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 z-50 w-80 max-w-[85vw] bg-[var(--surface)] border-r border-border shadow-xl overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Conversations
              </span>
              <button
                type="button"
                onClick={() => setMobileSidebarOpen(false)}
                className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:text-white"
              >
                <X className="size-4" strokeWidth={1.75} />
              </button>
            </div>
            <div className="p-3">
              <ConversationSidebar
                conversations={showArchived ? archivedConversations : conversations}
                activeConversationId={conversationId}
                loading={loadingConversations}
                onSelectConversation={(id) => {
                  handleSelectConversation(id);
                  setMobileSidebarOpen(false);
                  setShowArchived(false);
                }}
                onNewConversation={() => {
                  handleNewConversation();
                  setMobileSidebarOpen(false);
                  setShowArchived(false);
                }}
                onDeleteConversation={handleDeleteConversation}
                onSearch={showArchived ? undefined : handleSearchConversations}
                renameId={renameId}
                renameValue={renameValue}
                onRenameStart={(id, title) => {
                  setRenameId(id);
                  setRenameValue(title);
                }}
                onRenameChange={setRenameValue}
                onRenameConfirm={() => {
                  if (renameId && renameValue.trim()) {
                    handleRenameConversation(renameId, renameValue.trim());
                  }
                }}
                onRenameCancel={() => {
                  setRenameId(null);
                  setRenameValue("");
                }}
                deleteConfirmId={deleteConfirmId}
                onDeleteRequest={setDeleteConfirmId}
                onDeleteCancel={() => setDeleteConfirmId(null)}
                onArchiveConversation={showArchived ? undefined : handleArchiveConversation}
                archivedConversations={archivedConversations}
                onShowArchived={handleShowArchived}
              />
            </div>
          </div>
        </div>
      )}

      <div className="flex gap-0">
        {/* Sidebar — hidden on smaller screens */}
        <div className="hidden xl:flex xl:w-72 xl:shrink-0">
          <div className="w-full border-r border-[var(--border)] p-3">
            <ConversationSidebar
              conversations={showArchived ? archivedConversations : conversations}
              activeConversationId={conversationId}
              loading={loadingConversations}
              onSelectConversation={(id) => {
                handleSelectConversation(id);
                setShowArchived(false);
              }}
              onNewConversation={() => {
                handleNewConversation();
                setShowArchived(false);
              }}
              onDeleteConversation={handleDeleteConversation}
              onSearch={showArchived ? undefined : handleSearchConversations}
              renameId={renameId}
              renameValue={renameValue}
              onRenameStart={(id, title) => {
                setRenameId(id);
                setRenameValue(title);
              }}
              onRenameChange={setRenameValue}
              onRenameConfirm={() => {
                if (renameId && renameValue.trim()) {
                  handleRenameConversation(renameId, renameValue.trim());
                }
              }}
              onRenameCancel={() => {
                setRenameId(null);
                setRenameValue("");
              }}
              deleteConfirmId={deleteConfirmId}
              onDeleteRequest={setDeleteConfirmId}
              onDeleteCancel={() => setDeleteConfirmId(null)}
              onArchiveConversation={showArchived ? undefined : handleArchiveConversation}
              archivedConversations={archivedConversations}
              onShowArchived={handleShowArchived}
            />
          </div>
        </div>

        <div className="flex min-w-0 flex-1">
          <div className="h-[calc(100vh-7rem)] w-full">
            <ConversationArea
              messages={messages}
              isWaiting={isWaiting}
              draft={draft}
              onDraftChange={setDraft}
              onSubmit={handleSubmit}
              onCancel={handleCancel}
              onCitationClick={setSelectedCitation}
              streamingMessageId={streamingMessageId}
              restoreNotice={restoreNotice}
            />
          </div>
        </div>
      </div>

      <SourcePreviewModal
        citation={selectedCitation}
        open={selectedCitation !== null}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  );
}
