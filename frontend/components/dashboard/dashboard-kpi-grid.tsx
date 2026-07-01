import { KpiCard } from "@/components/common/kpi-card";
import type { DashboardKpi } from "@/types/dashboard";

type DashboardKpiGridProps = {
  kpis: DashboardKpi[];
};

export function DashboardKpiGrid({ kpis }: DashboardKpiGridProps) {
  return (
    <section
      aria-label="Key performance indicators"
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6"
    >
      {kpis.map((kpi) => (
        <KpiCard key={kpi.id} {...kpi} />
      ))}
    </section>
  );
}
