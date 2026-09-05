"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";

import {
  ConversationArea,
  type Message,
} from "@/components/ai-workspace/copilot/conversation-area";
import { ConversationSidebar } from "@/components/ai-workspace/copilot/conversation-sidebar";
import type { RetrievalTraceState } from "@/components/ai-workspace/copilot/retrieval-trace";
import { SourcesPanel } from "@/components/ai-workspace/copilot/sources-panel";
import { DocumentPreviewDialog } from "@/components/knowledge/documents/document-preview-dialog";
import { useDocumentActions } from "@/hooks/use-document-actions";
import {
  CURATED_SUGGESTIONS,
  type Suggestion,
} from "@/components/ai-workspace/copilot/thread-empty-state";
import { CopilotBar } from "@/components/ai-workspace/copilot/copilot-bar";
import {
  ChatTimeoutError,
  StreamIncompleteError,
  archiveConversation,
  clearConversation,
  ensureSessionId,
  fetchMessages,
  fetchSessionConversation,
  listArchivedConversations,
  listConversations,
  renameConversation,
  rotateSessionId,
  saveConversationSnapshot,
  streamChatMessage,
} from "@/lib/api/chat";
import { getApiErrorMessage } from "@/lib/api/errors";
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

/**
 * Whether two citations point at the same retrieved passage.
 *
 * Identity is the chunk id. An unidentified chunk (`null`) matches nothing,
 * including another unidentified chunk — otherwise "missing" collapses into a
 * single value that everything compares equal to.
 */
function isSameCitation(
  a: Citation | undefined,
  b: Citation | undefined,
): boolean {
  if (!a?.chunk_id || !b?.chunk_id) return false;
  return a.chunk_id === b.chunk_id;
}

export function CopilotPageContent() {
  // Opening a cited source reuses the Documents page's preview stack —
  // same fetch, same dialog — so a citation lands on the real file rather
  // than on the passage the model was already shown.
  const {
    previewDocument,
    previewUrl,
    previewText,
    isPreviewLoading,
    closePreview,
    handlePreviewById,
    handleDownload,
    actionError: previewError,
    setActionError: setPreviewError,
  } = useDocumentActions();

  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isWaiting, setIsWaiting] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [allSources, setAllSources] = useState<string[]>([]);
  const [lastCitations, setLastCitations] = useState<Citation[]>([]);
  // Which inline reference is lit up, scoped to the turn that owns it.
  const [activeCitation, setActiveCitation] = useState<
    { messageId: string; index: number } | null
  >(null);
  const [expandedSourceIndex, setExpandedSourceIndex] = useState<number | null>(null);
  // A passage opened from an earlier turn is not in the panel's list, so it
  // gets pinned above it rather than silently doing nothing.
  const [pinnedCitation, setPinnedCitation] = useState<Citation | null>(null);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [archivedConversations, setArchivedConversations] = useState<ConversationItem[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [restoreNotice, setRestoreNotice] = useState<"not_found" | "incomplete" | null>(null);
  // Background failures that leave the chat itself usable. Each is shown
  // where its own data lives rather than as one page-wide error.
  const [sidebarError, setSidebarError] = useState<string | null>(null);
  const [snapshotWarning, setSnapshotWarning] = useState<string | null>(null);
  const turnIndexRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const streamingIdRef = useRef<string | null>(null);
  const traceRef = useRef<
    ((update: (current: RetrievalTraceState) => RetrievalTraceState) => void) | null
  >(null);
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
            if (!cancelled) {
              setConversations(d.conversations);
              setSidebarError(null);
            }
          }).catch(async (listError) => {
            if (cancelled) return;
            setSidebarError(
              await getApiErrorMessage(
                listError,
                "Could not load your conversation list.",
              ),
            );
          });
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

  const handleRetryConversations = useCallback(async () => {
    setSidebarError(null);
    try {
      const data = await listConversations();
      setConversations(data.conversations);
    } catch (retryError) {
      setSidebarError(
        await getApiErrorMessage(
          retryError,
          "Could not load your conversation list.",
        ),
      );
    }
  }, []);

  const handleCitationSelect = useCallback(
    (messageId: string, index: number, citation?: Citation) => {
      setActiveCitation((prev) =>
        prev && prev.messageId === messageId && prev.index === index
          ? null
          : { messageId, index },
      );

      // The panel lists the latest turn. A passage from an older turn is not
      // in that list, so pin it instead of expanding the wrong row.
      //
      // This has to be an identity check on the chunk. While `chunk_id` was a
      // `str` defaulting to "", every citation carried "" and this compared
      // equal for any index that existed — so passages from older turns were
      // taken for current ones and the panel expanded the wrong row. A null id
      // means the chunk is unidentified, and two unidentified chunks are not
      // thereby the same chunk, so it never matches.
      const inPanel = citation != null && isSameCitation(lastCitations[index], citation);
      setPinnedCitation(inPanel || citation == null ? null : citation);
      setExpandedSourceIndex(inPanel ? index : null);
    },
    [lastCitations],
  );

  // `overrideQuestion` lets a suggestion or a retry submit text that is not
  // in the draft box yet — reading `draft` here would see the pre-update value.
  const handleSubmit = useCallback(async (overrideQuestion?: string) => {
    const question = (overrideQuestion ?? draft).trim();
    if (!question || isWaiting) return;
    if (messages.length > 0) {
      const last = messages[messages.length - 1];
      if (last.role === "user" && last.content === question) return;
    }

    setDraft("");
    setSnapshotWarning(null);
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content: question },
    ]);
    setIsWaiting(true);

    const assistantId = nextId();
    const startedAt = Date.now();
    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        trace: {
          phase: "retrieving",
          passageCount: 0,
          documentCount: 0,
          topScore: null,
          startedAt,
          finishedAt: null,
        },
      },
    ]);
    setStreamingMessageId(assistantId);
    streamingIdRef.current = assistantId;

    // Every trace update is driven by an SSE event the page already receives.
    const patchTrace = (
      update: (current: RetrievalTraceState) => RetrievalTraceState,
    ) =>
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId && msg.trace
            ? { ...msg, trace: update(msg.trace) }
            : msg,
        ),
      );
    traceRef.current = patchTrace;

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
            // Sources land before the first answer token — show them arriving.
            setActiveCitation(null);
            setPinnedCitation(null);
            setExpandedSourceIndex(null);
            patchTrace((trace) => ({
              ...trace,
              phase: data.citations.length === 0 ? "empty" : "composing",
              passageCount: data.citations.length,
              documentCount: data.sources.length,
            }));
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
          onEvidence(data) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? {
                      ...msg,
                      grounding: {
                        summary: data.evidence,
                        statements: data.classified_statements,
                      },
                    }
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
            patchTrace((trace) => ({
              ...trace,
              phase: trace.passageCount === 0 ? "empty" : "complete",
              topScore:
                typeof data.confidence === "number" ? data.confidence : null,
              finishedAt: Date.now(),
            }));
            // Save snapshot for this turn
            const currentConvId =
              conversationId ??
              (data as { conversation_id?: string }).conversation_id ??
              "";
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
              }).catch(() => {
                // The answer above is already on screen and saved; only the
                // per-turn detail snapshot failed, so warn without alarming.
                setSnapshotWarning(
                  "This turn's detail snapshot was not saved, so reopening this conversation may show less context.",
                );
              });
            }
            // Refresh conversation list to update message_count
            listConversations().then((convData) => {
              setConversations(convData.conversations);
              setSidebarError(null);
            }).catch(async (listError) => {
              setSidebarError(
                await getApiErrorMessage(
                  listError,
                  "Could not refresh your conversation list.",
                ),
              );
            });
          },
          onError(message) {
            setStreamingMessageId(null);
            patchTrace((trace) => ({
              ...trace,
              phase: "error",
              finishedAt: Date.now(),
            }));
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? {
                      ...msg,
                      isError: true,
                      notice: { kind: "error" as const, text: message },
                    }
                  : msg,
              ),
            );
          },
        },
        controller.signal,
      );
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setStreamingMessageId(null);
      patchTrace((trace) => ({ ...trace, phase: "error", finishedAt: Date.now() }));

      let message: string;
      if (err instanceof ChatTimeoutError) {
        message =
          "The request timed out. The AI service may be busy or unavailable — please try again.";
      } else if (err instanceof StreamIncompleteError) {
        message =
          "The connection dropped before the answer finished. The text above may be incomplete — please try again.";
      } else {
        message = "Sorry, a server error occurred. Please try again.";
      }

      // Tokens already on screen are real output. The failure is carried
      // alongside them rather than written into the answer, so a partial
      // answer stays clean markdown and the notice stays a notice.
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? {
                ...msg,
                isError: true,
                notice: { kind: "error" as const, text: message },
              }
            : msg,
        ),
      );
    } finally {
      setIsWaiting(false);
      abortRef.current = null;
      traceRef.current = null;
      streamingIdRef.current = null;
    }
  }, [draft, isWaiting, conversationId]);

  const handleRetryMessage = useCallback(
    (assistantMessageId: string) => {
      const index = messages.findIndex((m) => m.id === assistantMessageId);
      if (index < 1) return;
      for (let i = index - 1; i >= 0; i -= 1) {
        if (messages[i].role === "user") {
          handleSubmit(messages[i].content);
          return;
        }
      }
    },
    [messages, handleSubmit],
  );

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    traceRef.current?.((trace) => ({
      ...trace,
      phase: "cancelled",
      finishedAt: Date.now(),
    }));
    const cancelledId = streamingIdRef.current;
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === cancelledId
          ? {
              ...msg,
              notice: {
                kind: "cancelled" as const,
                text: msg.content.trim()
                  ? "You stopped this response. The text above is what had arrived."
                  : "You stopped this response before it started.",
              },
            }
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
    setActiveCitation(null);
    setPinnedCitation(null);
    setExpandedSourceIndex(null);
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

  // Grounded in what this account has actually asked. No history yet means a
  // first-run user, who gets the curated industrial prompts instead.
  const suggestions = useMemo<Suggestion[]>(() => {
    const fromHistory = conversations
      .filter((c) => (c.title ?? "").trim().length > 0 && c.message_count > 0)
      .slice(0, 4)
      .map((c) => ({
        id: c.id,
        text: (c.title as string).trim(),
        source: "history" as const,
      }));
    return fromHistory.length > 0 ? fromHistory : CURATED_SUGGESTIONS;
  }, [conversations]);

  const activeConversation =
    conversations.find((c) => c.id === conversationId) ??
    archivedConversations.find((c) => c.id === conversationId) ??
    null;
  const turnCount = messages.filter((m) => m.role === "assistant").length;

  // The rail is rendered twice — docked on wide screens and inside a sheet on
  // narrow ones. Only the post-action behaviour differs, so it is built once.
  function renderRail(onAfterAction?: () => void) {
    return (
      <ConversationSidebar
        conversations={showArchived ? archivedConversations : conversations}
        activeConversationId={conversationId}
        loading={loadingConversations}
        onSelectConversation={(id) => {
          handleSelectConversation(id);
          setShowArchived(false);
          onAfterAction?.();
        }}
        onNewConversation={() => {
          handleNewConversation();
          setShowArchived(false);
          onAfterAction?.();
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
        error={sidebarError}
        onRetry={handleRetryConversations}
      />
    );
  }

  function renderSources() {
    return (
      <SourcesPanel
        citations={lastCitations}
        sources={allSources}
        expandedIndex={expandedSourceIndex}
        onToggle={setExpandedSourceIndex}
        pinned={pinnedCitation}
        onClearPinned={() => setPinnedCitation(null)}
        onOpenDocument={handlePreviewById}
      />
    );
  }

  return (
    <div className="flex h-[calc(100vh-5rem)] min-h-[520px] w-full flex-col gap-2">
      <CopilotBar
        title={activeConversation?.title ?? null}
        turnCount={turnCount}
        sourceCount={allSources.length}
        hasConversation={conversationId !== null}
        deleteConfirmOpen={deleteConfirmId === "__all__"}
        onNewConversation={handleNewConversation}
        onDeleteRequest={() => setDeleteConfirmId("__all__")}
        onDeleteCancel={() => setDeleteConfirmId(null)}
        onDeleteAll={async () => {
          const { clearAllConversations } = await import("@/lib/api/chat");
          await clearAllConversations();
          setDeleteConfirmId(null);
          handleNewConversation();
        }}
        onOpenRail={() => setMobileSidebarOpen(true)}
        onOpenSources={() => setSourcesOpen(true)}
      />

      {/* Conversations sheet — narrow viewports */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 xl:hidden">
          <div
            className="fixed inset-0 bg-black/60"
            onClick={() => setMobileSidebarOpen(false)}
            role="presentation"
          />
          <div className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r border-border bg-[var(--surface)] shadow-2xl">
            <div className="flex h-9 shrink-0 items-center justify-between border-b border-border px-3">
              <span className="section-label">Conversations</span>
              <button
                type="button"
                onClick={() => setMobileSidebarOpen(false)}
                className="inline-flex size-6 items-center justify-center rounded text-muted-foreground transition-industrial hover:text-foreground"
                aria-label="Close conversations"
              >
                <X className="size-3.5" strokeWidth={1.75} />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden">
              {renderRail(() => setMobileSidebarOpen(false))}
            </div>
          </div>
        </div>
      )}

      {/* Sources sheet — narrow viewports */}
      {sourcesOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="fixed inset-0 bg-black/60"
            onClick={() => setSourcesOpen(false)}
            role="presentation"
          />
          <div className="fixed inset-y-0 right-0 z-50 flex w-96 max-w-[90vw] flex-col border-l border-border bg-[var(--surface)] shadow-2xl">
            <div className="flex h-9 shrink-0 items-center justify-between border-b border-border px-3">
              <span className="section-label">Sources</span>
              <button
                type="button"
                onClick={() => setSourcesOpen(false)}
                className="inline-flex size-6 items-center justify-center rounded text-muted-foreground transition-industrial hover:text-foreground"
                aria-label="Close sources"
              >
                <X className="size-3.5" strokeWidth={1.75} />
              </button>
            </div>
            <div className="flex min-h-0 flex-1 flex-col p-2">
              {renderSources()}
            </div>
          </div>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[212px_minmax(0,1fr)_336px]">
        <aside className="hidden min-h-0 overflow-hidden rounded-lg border border-border bg-[var(--surface)] xl:flex xl:flex-col">
          {renderRail()}
        </aside>

        <main className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-[var(--surface)]">
          {snapshotWarning && (
            <div className="flex shrink-0 items-start justify-between gap-3 border-b border-amber-500/20 bg-amber-500/10 px-3 py-2">
              <p className="text-[11px] leading-snug text-amber-300">
                {snapshotWarning}
              </p>
              <button
                type="button"
                onClick={() => setSnapshotWarning(null)}
                className="shrink-0 text-amber-300/70 transition-industrial hover:text-amber-200"
                aria-label="Dismiss"
              >
                <X className="size-3.5" strokeWidth={1.75} />
              </button>
            </div>
          )}
          <ConversationArea
            messages={messages}
            isWaiting={isWaiting}
            draft={draft}
            onDraftChange={setDraft}
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            onCitationSelect={handleCitationSelect}
            onOpenDocument={handlePreviewById}
            activeCitation={activeCitation}
            streamingMessageId={streamingMessageId}
            restoreNotice={restoreNotice}
            onDismissRestoreNotice={() => setRestoreNotice(null)}
            suggestions={suggestions}
            onRetryMessage={handleRetryMessage}
          />
        </main>

        <aside className="hidden min-h-0 lg:flex lg:flex-col">
          {renderSources()}
        </aside>
      </div>

      {previewError && (
        <div
          role="alert"
          className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-[12px] text-destructive"
        >
          {previewError}
          <button
            type="button"
            onClick={() => setPreviewError(null)}
            className="ml-3 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <DocumentPreviewDialog
        open={previewDocument !== null}
        document={previewDocument}
        previewUrl={previewUrl}
        previewText={previewText}
        isLoading={isPreviewLoading}
        onClose={closePreview}
        onDownload={handleDownload}
      />
    </div>
  );
}
