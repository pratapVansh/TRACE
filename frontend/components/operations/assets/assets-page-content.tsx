"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertTriangle, Cog, MapPin } from "lucide-react";

import { PageHeader } from "@/components/common/page-header";
import { DataTable } from "@/components/operations/data-table";
import { healthStatusBadge } from "@/components/operations/operations-badge";
import { StatCard } from "@/components/operations/stat-card";
import { KnowledgeSearchBar } from "@/components/knowledge/knowledge-search-bar";
import { APP_ROUTES } from "@/lib/auth/routes";
import { INDUSTRIAL_ASSETS } from "@/lib/operations/mock-data";
import type { IndustrialAsset } from "@/types/operations";

export function AssetsPageContent() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return INDUSTRIAL_ASSETS;
    return INDUSTRIAL_ASSETS.filter(
      (asset) =>
        asset.tag.toLowerCase().includes(q) ||
        asset.name.toLowerCase().includes(q) ||
        asset.location.toLowerCase().includes(q) ||
        asset.equipmentType.toLowerCase().includes(q),
    );
  }, [query]);

  const stats = useMemo(() => {
    const critical = INDUSTRIAL_ASSETS.filter((a) => a.healthStatus === "critical").length;
    const overdue = INDUSTRIAL_ASSETS.filter((a) =>
      a.maintenanceDue.toLowerCase().includes("overdue"),
    ).length;
    return { total: INDUSTRIAL_ASSETS.length, critical, overdue };
  }, []);

  const columns = [
    {
      key: "asset",
      header: "Asset",
      render: (row: IndustrialAsset) => (
        <div className="space-y-1">
          <p className="font-medium text-white">{row.tag}</p>
          <p className="max-w-xs text-xs text-muted-foreground">{row.name}</p>
        </div>
      ),
    },
    {
      key: "type",
      header: "Equipment Type",
      render: (row: IndustrialAsset) => (
        <span className="text-muted-foreground">{row.equipmentType}</span>
      ),
    },
    {
      key: "location",
      header: "Location",
      render: (row: IndustrialAsset) => (
        <span className="text-muted-foreground">{row.location}</span>
      ),
    },
    {
      key: "health",
      header: "Health Status",
      render: (row: IndustrialAsset) => healthStatusBadge(row.healthStatus),
    },
    {
      key: "maintenance",
      header: "Maintenance Due",
      render: (row: IndustrialAsset) => (
        <span
          className={
            row.maintenanceDue.toLowerCase().includes("overdue")
              ? "font-medium text-[var(--danger)]"
              : "text-muted-foreground"
          }
        >
          {row.maintenanceDue}
        </span>
      ),
    },
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="Industrial Operations"
        title="Assets"
        description="Monitor registered equipment tags, health status, and maintenance schedules across Northfield Refinery Complex."
        action={
          <Link
            href={APP_ROUTES.assetHierarchy}
            className="inline-flex h-10 items-center rounded-xl border border-border px-4 text-sm font-medium text-foreground transition-industrial hover:bg-[var(--surface)]"
          >
            View hierarchy
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Total Assets" value={String(stats.total)} icon={Cog} />
        <StatCard
          label="Critical Health"
          value={String(stats.critical)}
          hint="Requires immediate attention"
          icon={AlertTriangle}
          tone="danger"
        />
        <StatCard
          label="Overdue Maintenance"
          value={String(stats.overdue)}
          hint="Past scheduled date"
          icon={MapPin}
          tone="warning"
        />
      </div>

      <KnowledgeSearchBar
        value={query}
        onChange={setQuery}
        placeholder="Search by tag, name, location, or equipment type…"
      />

      <DataTable
        columns={columns}
        data={filtered}
        rowKey={(row) => row.id}
        minWidth="900px"
        footer={`Showing ${filtered.length} of ${INDUSTRIAL_ASSETS.length} assets`}
      />
    </div>
  );
}
