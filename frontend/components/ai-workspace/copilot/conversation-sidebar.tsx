"use client";

import { useCallback, useRef, useState } from "react";
import { Check, MessageSquare, Pencil, Plus, Search, Trash2, X } from "lucide-react";

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
          <div className="size-3.5 rounded bg-white/10" />
          <div className="h-3 flex-1 rounded bg-white/10" />
          <div className="size-4 rounded bg-white/10" />
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
    <div className="flex h-full flex-col gap-2">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Conversations
        </span>
        <button
          type="button"
          onClick={onNewConversation}
          className="inline-flex size-6 items-center justify-center rounded-md text-muted-foreground transition-industrial hover:bg-[var(--surface-tertiary)] hover:text-white"
          title="New conversation"
        >
          <Plus className="size-4" strokeWidth={1.75} />
        </button>
      </div>

      {/* Search */}
      {onSearch && (
        <div className="relative px-2 pb-2">
          <Search
            size={14}
            className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground/50"
          />
          <input
            type="text"
            value={searchLocal}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search conversations..."
            className="w-full rounded-lg border border-border bg-[var(--surface-tertiary)] py-1.5 pl-8 pr-3 text-xs text-white placeholder-muted-foreground/50 outline-none transition-colors focus:border-primary/30"
          />
          {searchLocal && (
            <button
              type="button"
              onClick={() => {
                setSearchLocal("");
                onSearch("");
              }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/50 hover:text-white"
            >
              <X className="size-3" strokeWidth={1.75} />
            </button>
          )}
        </div>
      )}

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <SidebarSkeleton />
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-4 py-12 text-center">
            <div className="flex size-10 items-center justify-center rounded-full bg-[var(--surface-tertiary)]">
              <MessageSquare className="size-5 text-muted-foreground" strokeWidth={1.5} />
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {searchLocal ? "No conversations match your search." : "No conversations yet."}
            </p>
            <button
              type="button"
              onClick={onNewConversation}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-[var(--surface-secondary)] px-3 py-1.5 text-xs font-medium text-muted-foreground transition-industrial hover:border-[var(--accent-steel)]/25 hover:text-white"
            >
              <Plus className="size-3.5" strokeWidth={1.75} />
              Start a new chat
            </button>
          </div>
        ) : (
          <ul className="flex flex-col gap-0.5 px-2">
            {conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              const isRenaming = renameId === conv.id;
              const isDeleting = deleteConfirmId === conv.id;

              return (
                <li key={conv.id}>
                  {isRenaming ? (
                    <div className="flex items-center gap-1 rounded-lg bg-[var(--surface-tertiary)] px-3 py-1.5">
                      <input
                        type="text"
                        value={renameValue ?? conv.title ?? ""}
                        onChange={(e) => onRenameChange?.(e.target.value)}
                        className="flex-1 bg-transparent text-xs text-white outline-none"
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
                        className="flex size-5 items-center justify-center rounded text-muted-foreground hover:text-white"
                        title="Cancel"
                      >
                        <X className="size-3.5" strokeWidth={1.75} />
                      </button>
                    </div>
                  ) : isDeleting ? (
                    <div className="flex items-center gap-1 rounded-lg border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-3 py-1.5">
                      <span className="flex-1 text-xs text-[var(--danger)] truncate">
                        Delete "{conv.title || "Untitled"}"?
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
                        className="flex size-5 items-center justify-center rounded text-muted-foreground hover:text-white"
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
                          "flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-left text-xs transition-industrial",
                          isActive
                            ? "bg-[var(--accent-steel)]/10 text-white"
                            : "text-muted-foreground hover:bg-[var(--surface-tertiary)] hover:text-white",
                        )}
                      >
                        <MessageSquare
                          className={cn(
                            "size-3.5 shrink-0",
                            isActive
                              ? "text-[var(--accent-steel)]"
                              : "text-muted-foreground/60 group-hover:text-muted-foreground",
                          )}
                          strokeWidth={1.75}
                        />
                        <span className="flex-1 truncate">
                          {conv.title || "Untitled"}
                        </span>
                        <div className="flex items-center gap-1">
                          <span className="text-[10px] tabular-nums text-muted-foreground/50">
                            {conv.message_count}
                          </span>
                          <span className="hidden text-[10px] text-muted-foreground/40 group-hover:inline">
                            {formatDate(conv.updated_at)}
                          </span>
                        </div>
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRenameStart?.(conv.id, conv.title || "Untitled");
                        }}
                        className="flex size-5 items-center justify-center rounded opacity-0 transition-industrial group-hover:opacity-100 text-muted-foreground hover:text-white"
                        title="Rename conversation"
                      >
                        <Pencil className="size-3" strokeWidth={1.75} />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteRequest?.(conv.id);
                        }}
                        className="flex size-5 items-center justify-center rounded opacity-0 transition-industrial group-hover:opacity-100 text-muted-foreground hover:text-[var(--danger)]"
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
    </div>
  );
}