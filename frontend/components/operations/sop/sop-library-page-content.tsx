"use client";

import { useMemo, useState } from "react";
import { BookOpen } from "lucide-react";

import { PageHeader } from "@/components/common/page-header";
import { KnowledgeSearchBar } from "@/components/knowledge/knowledge-search-bar";
import { DataTable } from "@/components/operations/data-table";
import { OperationsBadge } from "@/components/operations/operations-badge";
import { StatCard } from "@/components/operations/stat-card";
import { SOP_LIBRARY } from "@/lib/operations/mock-data";
import type { SopDocument } from "@/types/operations";

const SOP_STATUS_LABEL = {
  active: "Active",
  draft: "Draft",
  review: "In Review",
  archived: "Archived",
} as const;

export function SopLibraryPageContent() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return SOP_LIBRARY;
    return SOP_LIBRARY.filter(
      (sop) =>
        sop.code.toLowerCase().includes(q) ||
        sop.title.toLowerCase().includes(q) ||
        sop.category.toLowerCase().includes(q) ||
        sop.department.toLowerCase().includes(q),
    );
  }, [query]);

  const activeCount = SOP_LIBRARY.filter((s) => s.status === "active").length;

  const columns = [
    {
      key: "code",
      header: "SOP Code",
      render: (row: SopDocument) => (
        <span className="font-mono text-xs text-[var(--accent-steel-muted)]">{row.code}</span>
      ),
    },
    {
      key: "title",
      header: "Title",
      render: (row: SopDocument) => (
        <p className="max-w-sm font-medium text-white">{row.title}</p>
      ),
    },
    {
      key: "category",
      header: "Category",
      render: (row: SopDocument) => (
        <span className="text-muted-foreground">{row.category}</span>
      ),
    },
    {
      key: "version",
      header: "Version",
      render: (row: SopDocument) => (
        <span className="font-mono text-xs text-white">{row.version}</span>
      ),
    },
    {
      key: "department",
      header: "Department",
      render: (row: SopDocument) => (
        <span className="text-muted-foreground">{row.department}</span>
      ),
    },
    {
      key: "approved",
      header: "Approved By",
      render: (row: SopDocument) => (
        <span className="text-muted-foreground">{row.approvedBy}</span>
      ),
    },
    {
      key: "reviewed",
      header: "Last Reviewed",
      render: (row: SopDocument) => (
        <span className="text-muted-foreground">{row.lastReviewed}</span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (row: SopDocument) => {
        const variantMap = {
          active: "success",
          draft: "warning",
          review: "review",
          archived: "offline",
        } as const;
        return (
          <OperationsBadge
            variant={variantMap[row.status]}
            label={SOP_STATUS_LABEL[row.status]}
          />
        );
      },
    },
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="Industrial Operations"
        title="SOP Library"
        description="Approved standard operating procedures for operations, maintenance, safety, and inspection workflows."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Total SOPs" value={String(SOP_LIBRARY.length)} icon={BookOpen} />
        <StatCard
          label="Active"
          value={String(activeCount)}
          hint="Approved for use"
          icon={BookOpen}
          tone="success"
        />
        <StatCard
          label="Under Review / Draft"
          value={String(SOP_LIBRARY.length - activeCount)}
          icon={BookOpen}
          tone="warning"
        />
      </div>

      <KnowledgeSearchBar
        value={query}
        onChange={setQuery}
        placeholder="Search by code, title, category, or department…"
      />

      <DataTable
        columns={columns}
        data={filtered}
        rowKey={(row) => row.id}
        minWidth="1100px"
        footer={`Showing ${filtered.length} of ${SOP_LIBRARY.length} procedures`}
      />
    </div>
  );
}
