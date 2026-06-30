"use client";

import {
  ClipboardList,
  Cog,
  FileText,
  ShieldCheck,
} from "lucide-react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BackendStatus } from "@/components/common/backend-status";
import { KpiCard } from "@/components/common/kpi-card";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";

const KPI_DATA = [
  {
    title: "Documents",
    value: "12,847",
    change: "+284 indexed this quarter",
    changeType: "positive" as const,
    icon: FileText,
  },
  {
    title: "Assets",
    value: "2,416",
    change: "Across 14 production units",
    changeType: "neutral" as const,
    icon: Cog,
  },
  {
    title: "Compliance",
    value: "98.2%",
    change: "3 items require review",
    changeType: "warning" as const,
    icon: ShieldCheck,
  },
  {
    title: "Maintenance Tasks",
    value: "47",
    change: "12 scheduled this week",
    changeType: "neutral" as const,
    icon: ClipboardList,
  },
];

function DashboardContent() {
  const { user } = useAuth();

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 lg:gap-10">
      <section className="space-y-4">
        <p className="section-label">Overview</p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <h2 className="page-title">Welcome back, {user?.full_name}</h2>
            <p className="page-subtitle max-w-2xl">
              Monitor technical records, asset coverage, and compliance posture
              across your industrial operations environment.
            </p>
          </div>
          <Badge variant="success">Session active</Badge>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {KPI_DATA.map((kpi) => (
          <KpiCard key={kpi.title} {...kpi} />
        ))}
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <section className="industrial-card p-6 sm:p-8">
          <div className="mb-6 flex items-center justify-between gap-4">
            <div>
              <p className="section-label">Account</p>
              <h3 className="mt-2 text-xl font-semibold text-white">
                Operator profile
              </h3>
            </div>
            <Badge>{user?.role}</Badge>
          </div>

          <dl className="grid gap-4 sm:grid-cols-2">
            {[
              { label: "Email", value: user?.email },
              { label: "Role", value: user?.role },
              {
                label: "Status",
                value: user?.is_active ? "Active" : "Inactive",
              },
              {
                label: "Member since",
                value: user?.created_at
                  ? new Date(user.created_at).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })
                  : "—",
              },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-xl border border-border bg-[var(--surface-secondary)] p-4"
              >
                <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                  {label}
                </dt>
                <dd className="mt-2 text-sm font-medium text-white">{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="industrial-card p-6 sm:p-8">
          <div className="mb-6">
            <p className="section-label">Infrastructure</p>
            <h3 className="mt-2 text-xl font-semibold text-white">
              Platform status
            </h3>
          </div>
          <BackendStatus />
        </section>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AuthGuard>
      <DashboardLayout>
        <DashboardContent />
      </DashboardLayout>
    </AuthGuard>
  );
}
