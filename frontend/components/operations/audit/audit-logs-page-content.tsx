"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ScrollText } from "lucide-react";

import { PageHeader } from "@/components/common/page-header";
import { formatDateTime } from "@/lib/dashboard/format";
import { KnowledgeSearchBar } from "@/components/knowledge/knowledge-search-bar";
import { DataTable } from "@/components/operations/data-table";
import { OperationsBadge } from "@/components/operations/operations-badge";
import { StatCard } from "@/components/operations/stat-card";
import { APP_ROUTES } from "@/lib/auth/routes";
import { AUDIT_LOGS } from "@/lib/operations/mock-data";
import type { AuditLogEntry } from "@/types/operations";

export function AuditLogsPageContent() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return AUDIT_LOGS;
    return AUDIT_LOGS.filter(
      (log) =>
        log.user.toLowerCase().includes(q) ||
        log.action.toLowerCase().includes(q) ||
        log.resource.toLowerCase().includes(q) ||
        log.role.toLowerCase().includes(q),
    );
  }, [query]);

  const deniedCount = AUDIT_LOGS.filter((l) => l.outcome === "denied").length;

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
        <div className="space-y-1">
          <p className="font-medium text-white">{row.user}</p>
          <p className="text-xs text-muted-foreground">{row.role}</p>
        </div>
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
        <p className="max-w-xs text-sm text-white">{row.resource}</p>
      ),
    },
    {
      key: "outcome",
      header: "Outcome",
      render: (row: AuditLogEntry) => <OperationsBadge variant={row.outcome} />,
    },
    {
      key: "ip",
      header: "IP Address",
      render: (row: AuditLogEntry) => (
        <span className="font-mono text-xs text-muted-foreground">{row.ipAddress}</span>
      ),
    },
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="Industrial Operations"
        title="Audit Logs"
        description="Immutable activity trail for document access, work orders, compliance actions, and security events."
        action={
          <Link
            href={APP_ROUTES.compliance}
            className="inline-flex h-10 items-center rounded-xl border border-border px-4 text-sm font-medium text-foreground transition-industrial hover:bg-[var(--surface)]"
          >
            Compliance Center
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Total Events" value={String(AUDIT_LOGS.length)} icon={ScrollText} />
        <StatCard
          label="Successful"
          value={String(AUDIT_LOGS.filter((l) => l.outcome === "success").length)}
          tone="success"
          icon={ScrollText}
        />
        <StatCard
          label="Access Denied"
          value={String(deniedCount)}
          tone="danger"
          icon={ScrollText}
        />
      </div>

      <KnowledgeSearchBar
        value={query}
        onChange={setQuery}
        placeholder="Search by user, action, resource, or role…"
      />

      <DataTable
        columns={columns}
        data={filtered}
        rowKey={(row) => row.id}
        minWidth="1000px"
        footer={`Showing ${filtered.length} of ${AUDIT_LOGS.length} audit events`}
      />
    </div>
  );
}
