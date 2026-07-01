"use client";

import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";
import { formatDateTime } from "@/lib/dashboard/format";

type DashboardHeaderProps = {
  facilityName: string;
  lastUpdated: string;
};

export function DashboardHeader({ facilityName, lastUpdated }: DashboardHeaderProps) {
  const { user } = useAuth();

  return (
    <section className="space-y-4">
      <p className="section-label">Executive Overview</p>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-3">
          <h2 className="page-title">Welcome back, {user?.full_name}</h2>
          <p className="page-subtitle max-w-2xl">
            Real-time operational intelligence for {facilityName}. Monitor document
            coverage, asset health, compliance posture, and maintenance workload.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="success">Live dashboard</Badge>
          <Badge variant="secondary">{user?.role}</Badge>
          <span className="text-xs text-muted-foreground">
            Updated {formatDateTime(lastUpdated)}
          </span>
        </div>
      </div>
    </section>
  );
}
