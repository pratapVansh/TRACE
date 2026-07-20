"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_PREFIX = "trace_last_conv_";

/**
 * Manages conversation-ID persistence via URL (`?conv=<id>`) and localStorage.
 *
 * **Priority on mount:**
 *   1. URL search-param `conv`
 *   2. `localStorage` fallback
 *
 * **On `setConversationId`:**
 *   - Updates React state → triggers re-render
 *   - Updates URL via `history.replaceState` → no navigation, shareable link
 *   - Persists to `localStorage` → survives URL being cleared manually
 *
 * @param pageKey Unique key per page (e.g. `"copilot"`, `"agent-chat"`)
 */
export function useConversationPersistence(pageKey: string) {
  const storageKey = `${STORAGE_PREFIX}${pageKey}`;

  const [conversationId, setConversationIdRaw] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Guard against double-execution in StrictMode
  const didInit = useRef(false);

  // ── Read from URL / localStorage on mount ──────────────────────
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;

    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("conv");

    if (fromUrl) {
      setConversationIdRaw(fromUrl);
      // Also persist so it survives if the URL is wiped
      localStorage.setItem(storageKey, fromUrl);
    } else {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        setConversationIdRaw(stored);
        // Mirror into URL so the address bar is always up-to-date
        const url = new URL(window.location.href);
        url.searchParams.set("conv", stored);
        window.history.replaceState({}, "", url.toString());
      }
    }

    setIsInitialized(true);
  }, [storageKey]);

  // ── Setter that syncs state + URL + localStorage ───────────────
  const setConversationId = useCallback(
    (id: string | null) => {
      setConversationIdRaw(id);

      const url = new URL(window.location.href);

      if (id) {
        localStorage.setItem(storageKey, id);
        url.searchParams.set("conv", id);
      } else {
        localStorage.removeItem(storageKey);
        url.searchParams.delete("conv");
      }

      window.history.replaceState({}, "", url.toString());
    },
    [storageKey],
  );

  return { conversationId, setConversationId, isInitialized } as const;
}
