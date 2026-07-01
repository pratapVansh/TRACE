"use client";

import Link from "next/link";
import { ChevronDown, ChevronRight, Network } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/common/page-header";
import { healthStatusBadge } from "@/components/operations/operations-badge";
import { APP_ROUTES } from "@/lib/auth/routes";
import { ASSET_HIERARCHY } from "@/lib/operations/mock-data";
import { cn } from "@/lib/utils";
import type { AssetHierarchyNode } from "@/types/operations";

const TYPE_LABEL = {
  site: "Site",
  unit: "Production Unit",
  system: "System",
  equipment: "Equipment",
};

function HierarchyNode({
  node,
  depth = 0,
  defaultOpen = depth < 2,
}: {
  node: AssetHierarchyNode;
  depth?: number;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const hasChildren = Boolean(node.children?.length);

  return (
    <li>
      <div
        className={cn(
          "flex items-center gap-3 rounded-xl border border-border bg-[var(--surface-secondary)] px-4 py-3 transition-industrial hover:border-[var(--accent-steel)]/20",
          depth === 0 && "bg-[var(--surface)]",
        )}
        style={{ marginLeft: depth * 16 }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className="flex size-7 shrink-0 items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-white"
            aria-label={open ? "Collapse" : "Expand"}
          >
            {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          </button>
        ) : (
          <span className="size-7 shrink-0" />
        )}

        <div className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm font-medium text-white">{node.name}</p>
            <p className="text-xs text-muted-foreground">
              {TYPE_LABEL[node.type]}
              {node.tag ? ` · ${node.tag}` : ""}
              {node.assetCount ? ` · ${node.assetCount} assets` : ""}
            </p>
          </div>
          {node.healthStatus ? healthStatusBadge(node.healthStatus) : null}
        </div>
      </div>

      {hasChildren && open ? (
        <ul className="mt-2 space-y-2">
          {node.children!.map((child) => (
            <HierarchyNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function AssetHierarchyPageContent() {
  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="Industrial Operations"
        title="Asset Hierarchy"
        description="Explore the site → unit → system → equipment structure for Northfield Refinery Complex."
        action={
          <Link
            href={APP_ROUTES.assets}
            className="inline-flex h-10 items-center rounded-xl border border-border px-4 text-sm font-medium text-foreground transition-industrial hover:bg-[var(--surface)]"
          >
            Asset registry
          </Link>
        }
      />

      <div className="industrial-card p-5 sm:p-6">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg border border-border bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)]">
            <Network className="size-5" strokeWidth={1.75} />
          </div>
          <div>
            <p className="section-label">Structure</p>
            <h3 className="text-lg font-semibold text-white">Plant hierarchy</h3>
          </div>
        </div>

        <ul className="space-y-2">
          {ASSET_HIERARCHY.map((node) => (
            <HierarchyNode key={node.id} node={node} />
          ))}
        </ul>
      </div>
    </div>
  );
}
