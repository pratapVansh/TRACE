"use client";

import { useCallback, useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api/errors";
import { listAuditLogs, mapAuditLogFromApi } from "@/lib/api/audit-logs";
import type { AuditLogEntry } from "@/types/operations";

export const AUDIT_LOG_PAGE_SIZE = 50;

export type AuditLogQueryOptions = {
  user?: string;
  action?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
};

export function useAuditLogs(options: AuditLogQueryOptions = {}) {
  const page = options.page ?? 1;
  const pageSize = options.pageSize ?? AUDIT_LOG_PAGE_SIZE;

  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { user, action, dateFrom, dateTo } = options;
  const skip = (page - 1) * pageSize;

  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    // Declared inside the effect so the state updates below happen in the
    // async continuation rather than synchronously during the effect,
    // which is what turns this pattern into a render loop.
    const loadLogs = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await listAuditLogs({
          skip,
          limit: pageSize,
          user,
          action,
          dateFrom,
          dateTo,
        });

        if (cancelled) {
          return;
        }

        setLogs(response.items.map(mapAuditLogFromApi));
        setTotal(response.total);
        setTotalPages(response.total_pages);
      } catch (fetchError) {
        if (cancelled) {
          return;
        }

        setLogs([]);
        setTotal(0);
        setTotalPages(1);
        setError(await getApiErrorMessage(fetchError, "Failed to load audit logs."));
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadLogs();

    return () => {
      cancelled = true;
    };
  }, [action, dateFrom, dateTo, pageSize, reloadToken, skip, user]);

  const refresh = useCallback(() => {
    setReloadToken((token) => token + 1);
  }, []);

  return {
    logs,
    total,
    totalPages,
    page,
    pageSize,
    isLoading,
    error,
    refresh,
  };
}
