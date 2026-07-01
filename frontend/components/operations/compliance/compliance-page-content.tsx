"use client";

import Link from "next/link";
import { ClipboardCheck, ShieldCheck } from "lucide-react";

import { PageHeader } from "@/components/common/page-header";
import { MetricBar } from "@/components/dashboard/metric-bar";
import { DataTable } from "@/components/operations/data-table";
import {
  complianceStatusBadge,
  OperationsBadge,
} from "@/components/operations/operations-badge";
import { SectionCard } from "@/components/operations/section-card";
import { StatCard } from "@/components/operations/stat-card";
import { APP_ROUTES } from "@/lib/auth/routes";
import {
  AUDIT_SUMMARY,
  COMPLIANCE_SCORE,
  COMPLIANCE_STANDARDS,
} from "@/lib/operations/mock-data";
import type { AuditSummaryItem, ComplianceStandard } from "@/types/operations";

function scoreColor(score: number) {
  if (score >= 97) return "var(--success)";
  if (score >= 93) return "var(--accent-steel)";
  if (score >= 90) return "var(--warning)";
  return "var(--danger)";
}

export function CompliancePageContent() {
  const totalFindings = COMPLIANCE_STANDARDS.reduce(
    (sum, std) => sum + std.openFindings,
    0,
  );

  const auditColumns = [
    {
      key: "audit",
      header: "Audit",
      render: (row: AuditSummaryItem) => (
        <div className="space-y-1">
          <p className="font-medium text-white">{row.auditName}</p>
          <p className="text-xs text-muted-foreground">{row.auditor}</p>
        </div>
      ),
    },
    {
      key: "standard",
      header: "Standard",
      render: (row: AuditSummaryItem) => (
        <span className="text-muted-foreground">{row.standard}</span>
      ),
    },
    {
      key: "completed",
      header: "Completed",
      render: (row: AuditSummaryItem) => (
        <span className="text-muted-foreground">{row.completedAt}</span>
      ),
    },
    {
      key: "score",
      header: "Score",
      render: (row: AuditSummaryItem) => (
        <span className="font-medium text-white">{row.score}%</span>
      ),
    },
    {
      key: "findings",
      header: "Findings",
      render: (row: AuditSummaryItem) => (
        <span className="text-muted-foreground">{row.findings}</span>
      ),
    },
    {
      key: "status",
      header: "Result",
      render: (row: AuditSummaryItem) => (
        <OperationsBadge
          variant={
            row.status === "passed"
              ? "success"
              : row.status === "conditional"
                ? "warning"
                : "denied"
          }
          label={
            row.status === "passed"
              ? "Passed"
              : row.status === "conditional"
                ? "Conditional"
                : "Failed"
          }
        />
      ),
    },
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="Industrial Operations"
        title="Compliance Center"
        description="Monitor regulatory adherence across Factory Act, OISD, PESO, and ISO standards with audit summaries."
        action={
          <Link
            href={APP_ROUTES.auditLogs}
            className="inline-flex h-10 items-center rounded-xl border border-border px-4 text-sm font-medium text-foreground transition-industrial hover:bg-[var(--surface)]"
          >
            Audit logs
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          label="Compliance Score"
          value={`${COMPLIANCE_SCORE}%`}
          hint="Site-wide aggregate"
          icon={ShieldCheck}
          tone="success"
          className="sm:col-span-2 lg:col-span-1"
        />
        <StatCard
          label="Open Findings"
          value={String(totalFindings)}
          hint="Across all standards"
          icon={ClipboardCheck}
          tone="warning"
        />
        <StatCard
          label="Standards Tracked"
          value={String(COMPLIANCE_STANDARDS.length)}
          icon={ShieldCheck}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {COMPLIANCE_STANDARDS.map((standard: ComplianceStandard) => (
          <article
            key={standard.id}
            className="industrial-card space-y-4 p-5 sm:p-6"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-2xl font-semibold text-white">{standard.shortName}</p>
                <p className="mt-1 text-xs text-muted-foreground">{standard.name}</p>
              </div>
              {complianceStatusBadge(standard.status)}
            </div>
            <p className="text-3xl font-semibold text-white">{standard.score}%</p>
            <MetricBar
              label={standard.shortName}
              value={standard.score}
              color={scoreColor(standard.score)}
              showLabel={false}
            />
            <div className="space-y-1 text-xs text-muted-foreground">
              <p>Last audit: {standard.lastAudit}</p>
              <p>Next audit: {standard.nextAudit}</p>
              <p>{standard.openFindings} open finding{standard.openFindings === 1 ? "" : "s"}</p>
            </div>
          </article>
        ))}
      </div>

      <SectionCard
        sectionLabel="Audit Program"
        title="Audit summary"
        description="Recent internal and external compliance audits with scores and findings."
      >
        <DataTable
          columns={auditColumns}
          data={AUDIT_SUMMARY}
          rowKey={(row) => row.id}
          minWidth="900px"
        />
      </SectionCard>
    </div>
  );
}
