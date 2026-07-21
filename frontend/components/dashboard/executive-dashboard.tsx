"use client";

import { useEffect, useMemo, useState } from "react";
import { Database, FileText, Layers, MessageSquare, RefreshCw } from "lucide-react";

import { AssetDistributionWidget } from "@/components/dashboard/asset-distribution-widget";
import { ComplianceOverviewWidget } from "@/components/dashboard/compliance-overview-widget";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { DashboardKpiGrid } from "@/components/dashboard/dashboard-kpi-grid";
import { NotificationsWidget } from "@/components/dashboard/notifications-widget";
import { QuickActionsWidget } from "@/components/dashboard/quick-actions-widget";
import { RecentActivityWidget } from "@/components/dashboard/recent-activity-widget";
import { RecentDocumentsWidget } from "@/components/dashboard/recent-documents-widget";
import { RecentSearchesWidget } from "@/components/dashboard/recent-searches-widget";
import { fetchDashboard, type DashboardApiResponse } from "@/lib/api/dashboard";
import { EXECUTIVE_DASHBOARD_DATA } from "@/lib/dashboard/mock-data";
import { useDocumentsContext, useRecentDocuments } from "@/hooks/use-documents";
import type { ExecutiveDashboardData, DashboardKpi } from "@/types/dashboard";

function buildKpis(api: DashboardApiResponse): DashboardKpi[] {
  const items: DashboardKpi[] = [
    {
      id: "total-documents",
      title: "Total Documents",
      value: api.document_count.toLocaleString(),
      change: `${api.document_count} document${api.document_count === 1 ? "" : "s"} in repository`,
      changeType: "neutral",
      icon: FileText,
    },
    {
      id: "graph-entities",
      title: "Graph Entities",
      value: api.entity_count != null ? api.entity_count.toLocaleString() : "N/A",
      change: api.neo4j_connected ? "Knowledge graph active" : "Graph store unavailable",
      changeType: api.neo4j_connected ? "positive" : "warning",
      icon: Layers,
    },
    {
      id: "graph-relationships",
      title: "Relationships",
      value: api.relationship_count != null ? api.relationship_count.toLocaleString() : "N/A",
      change: api.neo4j_connected ? "Connections in graph" : "Graph store unavailable",
      changeType: api.neo4j_connected ? "positive" : "warning",
      icon: Database,
    },
    {
      id: "conversations",
      title: "Conversations",
      value: api.conversation_count.toLocaleString(),
      change: `${api.conversation_count} conversation${api.conversation_count === 1 ? "" : "s"}`,
      changeType: "neutral",
      icon: MessageSquare,
    },
  ];

  if (api.pending_jobs > 0) {
    items.push({
      id: "pending-jobs",
      title: "Pending Jobs",
      value: String(api.pending_jobs),
      change: `${api.pending_jobs} job${api.pending_jobs === 1 ? "" : "s"} waiting`,
      changeType: "warning",
      icon: RefreshCw,
    });
  }

  return items;
}

export function ExecutiveDashboard() {
  const { queryVersion } = useDocumentsContext();
  const { documents: recentDocuments, isLoading: isDocumentsLoading, total } =
    useRecentDocuments(5);

  const [apiData, setApiData] = useState<DashboardApiResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchDashboard()
      .then((data) => {
        if (!cancelled) {
          setApiData(data);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [queryVersion]);

  const displayData: ExecutiveDashboardData = useMemo(() => {
    if (!apiData) return EXECUTIVE_DASHBOARD_DATA;

    const kpis = buildKpis(apiData);

    const recentActivity = apiData.recent_uploads.map((u) => ({
      id: u.id,
      action: "uploaded",
      subject: u.title,
      actor: "System",
      timestamp: u.uploaded_at,
      type: "document" as const,
    }));

    return {
      ...EXECUTIVE_DASHBOARD_DATA,
      lastUpdated: new Date().toISOString(),
      kpis,
      recentActivity,
      notifications: apiData.db_connected
        ? [
            {
              id: "n1",
              title: "System Status",
              message: apiData.qdrant_connected
                ? "All systems operational"
                : "Vector search unavailable",
              timestamp: new Date().toISOString(),
              priority: apiData.qdrant_connected ? "low" : "medium",
              read: false,
            },
          ]
        : [
            {
              id: "n1",
              title: "Database Issue",
              message: "Database connection unavailable",
              timestamp: new Date().toISOString(),
              priority: "high",
              read: false,
            },
          ],
    };
  }, [apiData]);

  const kpis = useMemo(
    () =>
      displayData.kpis.map((kpi) =>
        kpi.id === "total-documents"
          ? {
              ...kpi,
              value: isDocumentsLoading ? "..." : total.toLocaleString(),
              change: isDocumentsLoading
                ? "Loading document count..."
                : `${total} document${total === 1 ? "" : "s"} in repository`,
            }
          : kpi,
      ),
    [displayData.kpis, isDocumentsLoading, total],
  );

  if (loading) {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-8 lg:gap-10">
        <DashboardHeader facilityName="" lastUpdated="" />
        <div className="rounded-xl border border-border bg-[var(--surface-secondary)] p-8 text-center">
          <p className="text-sm text-muted-foreground">Loading dashboard data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-8 lg:gap-10">
      <DashboardHeader
        facilityName={displayData.facilityName}
        lastUpdated={displayData.lastUpdated}
      />

      {displayData.kpis.length > 0 ? (
        <DashboardKpiGrid kpis={kpis} />
      ) : (
        <div className="rounded-xl border border-border bg-[var(--surface-secondary)] p-8 text-center">
          <p className="text-sm text-muted-foreground">No KPI data available.</p>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-8">
          <RecentDocumentsWidget
            documents={recentDocuments}
            isLoading={isDocumentsLoading}
          />
        </div>
        <div className="xl:col-span-4">
          <NotificationsWidget notifications={displayData.notifications} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <RecentActivityWidget activities={displayData.recentActivity} />
        <ComplianceOverviewWidget metrics={displayData.complianceMetrics} />
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-5">
          <AssetDistributionWidget
            categories={displayData.assetCategories}
            totalAssets={0}
          />
        </div>
        <div className="xl:col-span-4">
          <RecentSearchesWidget searches={displayData.recentSearches} />
        </div>
        <div className="xl:col-span-3">
          <QuickActionsWidget actions={displayData.quickActions} />
        </div>
      </div>
    </div>
  );
}
