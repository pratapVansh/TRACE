"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ScrollText } from "lucide-react";

import { PageHeader } from "@/components/common/page-header";
import { formatDateTime } from "@/lib/dashboard/format";
import { KnowledgeSearchBar } from "@/components/knowledge/knowledge-search-bar";
import { DocumentPagination } from "@/components/knowledge/documents/document-pagination";
import { AuditLogFilters } from "@/components/operations/audit/audit-log-filters";
import { DataTable } from "@/components/operations/data-table";
import { OperationsBadge } from "@/components/operations/operations-badge";
import { StatCard } from "@/components/operations/stat-card";
import { Skeleton } from "@/components/ui/skeleton";
import { AUDIT_LOG_PAGE_SIZE, useAuditLogs } from "@/hooks/use-audit-logs";
import { APP_ROUTES } from "@/lib/auth/routes";
import {
  AUDIT_LOG_DEFAULT_FILTERS,
  type AuditLogFilterValues,
} from "@/lib/operations/constants";
import type { AuditLogEntry } from "@/types/operations";

export function AuditLogsPageContent() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [filters, setFilters] = useState(AUDIT_LOG_DEFAULT_FILTERS);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(query);
      setPage(1);
    }, 300);

    return () => window.clearTimeout(timer);
  }, [query]);

  // Reset to the first page on the change itself rather than in an effect
  // watching the filters — an effect that sets state re-renders to do it.
  const handleFiltersChange = (next: AuditLogFilterValues) => {
    setFilters(next);
    setPage(1);
  };

  const { logs, total, totalPages, isLoading, error } = useAuditLogs({
    user: debouncedQuery || undefined,
    action: filters.action !== "all" ? filters.action : undefined,
    // The date inputs give a bare day. Widening "to" to the end of that day
    // keeps a single-day range from matching only midnight exactly.
    dateFrom: filters.dateFrom ? `${filters.dateFrom}T00:00:00` : undefined,
    dateTo: filters.dateTo ? `${filters.dateTo}T23:59:59` : undefined,
    page,
    pageSize: AUDIT_LOG_PAGE_SIZE,
  });

  const failedOnPage = logs.filter((log) => log.outcome === "failure").length;

  const columns = [
    {
      key: "timestamp",
      header: "Timestamp",
      render: (row: AuditLogEntry) => (
        <span className="text-muted-foreground">{formatDateTime(row.timestamp)}</span>
      ),
    },
    {
      key: "user",
      header: "User",
      render: (row: AuditLogEntry) => (
        <p className="font-medium text-foreground">{row.user}</p>
      ),
    },
    {
      key: "action",
      header: "Action",
      render: (row: AuditLogEntry) => (
        <span className="text-muted-foreground">{row.action}</span>
      ),
    },
    {
      key: "resource",
      header: "Resource",
      render: (row: AuditLogEntry) => (
        <p className="max-w-xs text-sm text-foreground">{row.resource}</p>
      ),
    },
    {
      key: "outcome",
      header: "Outcome",
      render: (row: AuditLogEntry) => (
        <div className="space-y-1">
          <OperationsBadge
            variant={row.outcome === "success" ? "success" : "denied"}
            label={row.outcome === "success" ? "Success" : "Failure"}
          />
          {row.errorMessage ? (
            <p className="max-w-xs text-xs text-muted-foreground">{row.errorMessage}</p>
          ) : null}
        </div>
      ),
    },
    {
      key: "ip",
      header: "IP Address",
      render: (row: AuditLogEntry) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.ipAddress ?? "—"}
        </span>
      ),
    },
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="Industrial Operations"
        title="Audit Logs"
        description="Immutable activity trail for authentication, user management, and document processing events."
        action={
          <Link
            href={APP_ROUTES.documents}
            className="inline-flex h-10 items-center rounded-xl border border-border px-4 text-sm font-medium text-foreground transition-industrial hover:bg-[var(--surface)]"
          >
            Documents
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Total Events" value={String(total)} icon={ScrollText} />
        <StatCard label="On This Page" value={String(logs.length)} icon={ScrollText} />
        <StatCard
          label="Failures on This Page"
          value={String(failedOnPage)}
          tone="danger"
          icon={ScrollText}
        />
      </div>

      <KnowledgeSearchBar
        value={query}
        onChange={setQuery}
        placeholder="Filter by username…"
      />

      <AuditLogFilters filters={filters} onChange={handleFiltersChange} />

      {error ? (
        <div className="rounded-xl border border-[var(--danger)]/25 bg-[var(--danger)]/10 px-4 py-3 text-sm text-[var(--danger)]">
          {error}
        </div>
      ) : null}

      {isLoading ? (
        <div className="industrial-card space-y-3 p-6">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-0">
          <DataTable
            columns={columns}
            data={logs}
            rowKey={(row) => row.id}
            minWidth="1000px"
            emptyMessage={
              error
                ? "Audit logs could not be loaded."
                : "No audit events match this filter."
            }
          />
          {logs.length > 0 ? (
            <div className="industrial-card mt-4 overflow-hidden">
              <DocumentPagination
                page={page}
                totalPages={totalPages}
                total={total}
                pageSize={AUDIT_LOG_PAGE_SIZE}
                onPageChange={setPage}
                itemLabel="event"
              />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
