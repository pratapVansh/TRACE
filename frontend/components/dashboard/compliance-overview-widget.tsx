import { MetricBar } from "@/components/dashboard/metric-bar";
import { WidgetCard } from "@/components/dashboard/widget-card";
import { WidgetHeader } from "@/components/dashboard/widget-header";
import { Badge } from "@/components/ui/badge";
import type { ComplianceMetric } from "@/types/dashboard";

const STATUS_VARIANT = {
  compliant: "success",
  review: "warning",
  "at-risk": "default",
} as const;

const STATUS_LABEL = {
  compliant: "Compliant",
  review: "Under review",
  "at-risk": "At risk",
} as const;

const SCORE_COLOR = (score: number) => {
  if (score >= 98) return "var(--success)";
  if (score >= 95) return "var(--accent-steel)";
  if (score >= 90) return "var(--warning)";
  return "var(--danger)";
};

type ComplianceOverviewWidgetProps = {
  metrics: ComplianceMetric[];
};

export function ComplianceOverviewWidget({ metrics }: ComplianceOverviewWidgetProps) {
  const averageScore = Math.round(
    metrics.reduce((sum, metric) => sum + metric.score, 0) / metrics.length,
  );

  return (
    <WidgetCard>
      <WidgetHeader
        sectionLabel="Governance"
        title="Compliance Overview"
        description="Standards adherence across regulatory and internal audit programs."
        action={<Badge variant="success">{averageScore}% avg score</Badge>}
      />

      <div className="flex flex-1 flex-col gap-2.5">
        {metrics.map((metric) => (
          <div key={metric.id} className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[12px] font-medium text-foreground">{metric.standard}</p>
              <Badge variant={STATUS_VARIANT[metric.status]}>
                {STATUS_LABEL[metric.status]}
              </Badge>
            </div>
            <MetricBar
              label={metric.standard}
              value={metric.score}
              color={SCORE_COLOR(metric.score)}
              showLabel={false}
            />
            {metric.dueDate ? (
              <p className="text-xs text-muted-foreground">
                Next review:{" "}
                {new Date(metric.dueDate).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </WidgetCard>
  );
}
