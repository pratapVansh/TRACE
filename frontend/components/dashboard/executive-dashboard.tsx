"use client";

import { useMemo } from "react";

import { AssetDistributionWidget } from "@/components/dashboard/asset-distribution-widget";
import { ComplianceOverviewWidget } from "@/components/dashboard/compliance-overview-widget";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { DashboardKpiGrid } from "@/components/dashboard/dashboard-kpi-grid";
import { NotificationsWidget } from "@/components/dashboard/notifications-widget";
import { QuickActionsWidget } from "@/components/dashboard/quick-actions-widget";
import { RecentActivityWidget } from "@/components/dashboard/recent-activity-widget";
import { RecentDocumentsWidget } from "@/components/dashboard/recent-documents-widget";
import { RecentSearchesWidget } from "@/components/dashboard/recent-searches-widget";
import { useRecentDocuments } from "@/hooks/use-documents";
import { EXECUTIVE_DASHBOARD_DATA } from "@/lib/dashboard/mock-data";
import type { ExecutiveDashboardData } from "@/types/dashboard";

type ExecutiveDashboardProps = {
  data?: ExecutiveDashboardData;
};

export function ExecutiveDashboard({
  data = EXECUTIVE_DASHBOARD_DATA,
}: ExecutiveDashboardProps) {
  const { documents: recentDocuments, isLoading: isDocumentsLoading, total } =
    useRecentDocuments(5);

  const totalAssets = data.kpis.find((kpi) => kpi.id === "industrial-assets");
  const assetTotal = totalAssets
    ? Number.parseInt(totalAssets.value.replace(/,/g, ""), 10)
    : 0;

  const kpis = useMemo(
    () =>
      data.kpis.map((kpi) =>
        kpi.id === "total-documents"
          ? {
              ...kpi,
              value: isDocumentsLoading ? "…" : total.toLocaleString(),
              change: isDocumentsLoading
                ? "Loading document count…"
                : `${total} document${total === 1 ? "" : "s"} in repository`,
            }
          : kpi,
      ),
    [data.kpis, isDocumentsLoading, total],
  );

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-8 lg:gap-10">
      <DashboardHeader
        facilityName={data.facilityName}
        lastUpdated={data.lastUpdated}
      />

      <DashboardKpiGrid kpis={kpis} />

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-8">
          <RecentDocumentsWidget
            documents={recentDocuments}
            isLoading={isDocumentsLoading}
          />
        </div>
        <div className="xl:col-span-4">
          <NotificationsWidget notifications={data.notifications} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <RecentActivityWidget activities={data.recentActivity} />
        <ComplianceOverviewWidget metrics={data.complianceMetrics} />
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-5">
          <AssetDistributionWidget
            categories={data.assetCategories}
            totalAssets={assetTotal}
          />
        </div>
        <div className="xl:col-span-4">
          <RecentSearchesWidget searches={data.recentSearches} />
        </div>
        <div className="xl:col-span-3">
          <QuickActionsWidget actions={data.quickActions} />
        </div>
      </div>
    </div>
  );
}
