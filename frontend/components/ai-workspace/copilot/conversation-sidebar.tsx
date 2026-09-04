"use client";

import { useCallback, useRef, useState } from "react";
import { Archive, ArchiveRestore, Check, MessageSquare, Pencil, Plus, Search, Trash2, X } from "lucide-react";

import type { ConversationItem } from "@/types/chat";
import { cn } from "@/lib/utils";

interface ConversationSidebarProps {
  conversations: ConversationItem[];
  activeConversationId: string | null;
  loading: boolean;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onSearch?: (query: string) => void;
  renameId?: string | null;
  renameValue?: string;
  onRenameStart?: (id: string, title: string) => void;
  onRenameChange?: (value: string) => void;
  onRenameConfirm?: () => void;
  onRenameCancel?: () => void;
  deleteConfirmId?: string | null;
  onDeleteRequest?: (id: string | null) => void;
  onDeleteCancel?: () => void;
  onArchiveConversation?: (id: string) => void;
  archivedConversations?: ConversationItem[];
  onShowArchived?: () => void;
  error?: string | null;
  onRetry?: () => void;
}

function formatDate(ts: number): string {
  const d = new Date(ts * 1000);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / 86_400_000);

  if (diffDays === 0) {
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function SidebarSkeleton() {
  return (
    <div className="flex flex-col gap-2 px-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="flex h-9 animate-pulse items-center gap-2 rounded-lg bg-[var(--surface-tertiary)] px-3"
        >
          <div className="size-3.5 rounded bg-[var(--surface)]/10" />
          <div className="h-3 flex-1 rounded bg-[var(--surface)]/10" />
          <div className="size-4 rounded bg-[var(--surface)]/10" />
        </div>
      ))}
    </div>
  );
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  loading,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onSearch,
  renameId,
  renameValue,
  onRenameStart,
  onRenameChange,
  onRenameConfirm,
  onRenameCancel,
  deleteConfirmId,
  onDeleteRequest,
  onDeleteCancel,
  onArchiveConversation,
  archivedConversations,
  onShowArchived,
  error,
  onRetry,
}: ConversationSidebarProps) {
  const [searchLocal, setSearchLocal] = useState("");
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearchChange = useCallback((value: string) => {
    setSearchLocal(value);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => {
      onSearch?.(value);
    }, 300);
  }, [onSearch]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Header */}
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-border px-2">
        <span className="section-label">Conversations</span>
        <button
          type="button"
          onClick={onNewConversation}
          className="inline-flex size-5 items-center justify-center rounded text-muted-foreground transition-industrial hover:bg-[var(--surface-tertiary)] hover:text-foreground"
          title="New conversation"
        >
          <Plus className="size-3.5" strokeWidth={1.75} />
        </button>
      </div>

      {/* The list failed to refresh — say so instead of showing a stale
          or empty list as though it were current. */}
      {error && (
        <div className="mx-1.5 mt-1.5 rounded border border-[var(--danger)]/25 bg-[var(--danger)]/10 px-2 py-1.5">
          <p className="text-[11px] leading-snug text-[var(--danger)]">{error}</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-1 text-[11px] font-medium text-[var(--danger)] underline transition-industrial hover:text-red-300"
            >
              Retry
            </button>
          )}
        </div>
      )}

      {/* Search */}
      {onSearch && (
        <div className="relative shrink-0 px-1.5 py-1.5">
          <Search
            size={14}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground/50"
          />
          <input
            type="text"
            value={searchLocal}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Filter conversations"
            className="w-full rounded border border-border bg-[var(--surface-secondary)] py-1 pl-7 pr-3 text-[12px] text-foreground placeholder-muted-foreground/50 outline-none transition-industrial focus:border-[var(--accent-steel)]/40"
          />
          {searchLocal && (
            <button
              type="button"
              onClick={() => {
                setSearchLocal("");
                onSearch("");
              }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/50 transition-industrial hover:text-foreground"
            >
              <X className="size-3" strokeWidth={1.75} />
            </button>
          )}
        </div>
      )}

      {/* List */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <SidebarSkeleton />
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-start gap-2 px-2.5 py-6">
            <p className="text-[11px] leading-snug text-muted-foreground">
              {searchLocal ? "No conversations match your search." : "No conversations yet."}
            </p>
            <button
              type="button"
              onClick={onNewConversation}
              className="inline-flex items-center gap-1 rounded border border-border bg-[var(--surface-secondary)] px-2 py-1 text-[11px] font-medium text-muted-foreground transition-industrial hover:border-[var(--accent-steel)]/25 hover:text-foreground"
            >
              <Plus className="size-3" strokeWidth={1.75} />
              New inquiry
            </button>
          </div>
        ) : (
          <ul className="flex flex-col px-1.5 py-1">
            {conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              const isRenaming = renameId === conv.id;
              const isDeleting = deleteConfirmId === conv.id;

              return (
                <li key={conv.id}>
                  {isRenaming ? (
                    <div className="flex items-center gap-1 rounded bg-[var(--surface-tertiary)] px-2 py-1">
                      <input
                        type="text"
                        value={renameValue ?? conv.title ?? ""}
                        onChange={(e) => onRenameChange?.(e.target.value)}
                        className="flex-1 bg-transparent text-[12px] text-foreground outline-none"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === "Enter") onRenameConfirm?.();
                          if (e.key === "Escape") onRenameCancel?.();
                        }}
                      />
                      <button
                        type="button"
                        onClick={onRenameConfirm}
                        className="flex size-5 items-center justify-center rounded text-green-400 hover:text-green-300"
                        title="Save"
                      >
                        <Check className="size-3.5" strokeWidth={2} />
                      </button>
                      <button
                        type="button"
                        onClick={onRenameCancel}
                        className="flex size-5 items-center justify-center rounded text-muted-foreground hover:text-foreground"
                        title="Cancel"
                      >
                        <X className="size-3.5" strokeWidth={1.75} />
                      </button>
                    </div>
                  ) : isDeleting ? (
                    <div className="flex items-center gap-1 rounded border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-2 py-1">
                      <span className="flex-1 truncate text-[11px] text-[var(--danger)]">
                        Delete &quot;{conv.title || "Untitled"}&quot;?
                      </span>
                      <button
                        type="button"
                        onClick={() => onDeleteConversation(conv.id)}
                        className="flex size-5 items-center justify-center rounded text-[var(--danger)] hover:text-red-300"
                        title="Confirm delete"
                      >
                        <Check className="size-3.5" strokeWidth={2} />
                      </button>
                      <button
                        type="button"
                        onClick={onDeleteCancel}
                        className="flex size-5 items-center justify-center rounded text-muted-foreground hover:text-foreground"
                        title="Cancel"
                      >
                        <X className="size-3.5" strokeWidth={1.75} />
                      </button>
                    </div>
                  ) : (
                    <div className="group flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => onSelectConversation(conv.id)}
                        className={cn(
                          "flex min-w-0 flex-1 items-center gap-1.5 rounded px-2 py-1 text-left text-[12px] transition-industrial",
                          isActive
                            ? "bg-[var(--accent-steel)]/12 text-foreground"
                            : "text-muted-foreground hover:bg-[var(--surface-tertiary)] hover:text-foreground",
                        )}
                      >
                        <MessageSquare
                          className={cn(
                            "size-3 shrink-0",
                            isActive
                              ? "text-[var(--accent-steel)]"
                              : "text-muted-foreground/60 group-hover:text-muted-foreground",
                          )}
                          strokeWidth={1.75}
                        />
                        <span className="min-w-0 flex-1 truncate">{conv.title || "Untitled"}</span>
                        <span className="shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground/50">
                          {conv.message_count}
                        </span>
                        <span className="hidden shrink-0 font-mono text-[10px] text-muted-foreground/40 group-hover:inline">
                          {formatDate(conv.updated_at)}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRenameStart?.(conv.id, conv.title || "Untitled");
                        }}
                        className="flex size-5 shrink-0 items-center justify-center rounded opacity-0 transition-industrial group-hover:opacity-100 text-muted-foreground hover:text-foreground"
                        title="Rename conversation"
                      >
                        <Pencil className="size-3" strokeWidth={1.75} />
                      </button>
                      {onArchiveConversation && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onArchiveConversation(conv.id);
                          }}
                          className="flex size-5 shrink-0 items-center justify-center rounded opacity-0 transition-industrial group-hover:opacity-100 text-muted-foreground hover:text-amber-400"
                          title="Archive conversation"
                        >
                          <Archive className="size-3" strokeWidth={1.75} />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteRequest?.(conv.id);
                        }}
                        className="flex size-5 shrink-0 items-center justify-center rounded opacity-0 transition-industrial group-hover:opacity-100 text-muted-foreground hover:text-[var(--danger)]"
                        title="Delete conversation"
                      >
                        <Trash2 className="size-3" strokeWidth={1.75} />
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Archived section */}
      {onShowArchived && (archivedConversations ?? []).length > 0 && (
        <div className="shrink-0 border-t border-border p-1.5">
          <button
            type="button"
            onClick={onShowArchived}
            className="flex w-full items-center gap-1.5 rounded px-2 py-1 text-[11px] text-muted-foreground transition-industrial hover:bg-[var(--surface-tertiary)] hover:text-foreground"
          >
            <ArchiveRestore className="size-3" strokeWidth={1.75} />
            <span>Archived ({(archivedConversations ?? []).length})</span>
          </button>
        </div>
      )}
    </div>
  );
}