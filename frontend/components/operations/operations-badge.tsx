import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type OperationsBadgeVariant =
  | "healthy"
  | "degraded"
  | "critical"
  | "offline"
  | "critical_priority"
  | "high_priority"
  | "medium_priority"
  | "low_priority"
  | "open"
  | "in_progress"
  | "scheduled"
  | "completed"
  | "overdue"
  | "compliant"
  | "review"
  | "at_risk"
  | "non_compliant"
  | "success"
  | "denied"
  | "warning";

const VARIANT_STYLES: Record<
  OperationsBadgeVariant,
  { label: string; className?: string; variant: "success" | "warning" | "secondary" | "default" }
> = {
  healthy: { label: "Healthy", variant: "success" },
  degraded: { label: "Degraded", variant: "warning" },
  critical: { label: "Critical", variant: "default", className: "border-[var(--danger)]/25 bg-[var(--danger)]/10 text-[var(--danger)]" },
  offline: { label: "Offline", variant: "secondary" },
  critical_priority: { label: "Critical", variant: "default", className: "border-[var(--danger)]/25 bg-[var(--danger)]/10 text-[var(--danger)]" },
  high_priority: { label: "High", variant: "warning" },
  medium_priority: { label: "Medium", variant: "default" },
  low_priority: { label: "Low", variant: "secondary" },
  open: { label: "Open", variant: "default" },
  in_progress: { label: "In Progress", variant: "default" },
  scheduled: { label: "Scheduled", variant: "secondary" },
  completed: { label: "Completed", variant: "success" },
  overdue: { label: "Overdue", variant: "default", className: "border-[var(--danger)]/25 bg-[var(--danger)]/10 text-[var(--danger)]" },
  compliant: { label: "Compliant", variant: "success" },
  review: { label: "Under Review", variant: "warning" },
  at_risk: { label: "At Risk", variant: "warning" },
  non_compliant: { label: "Non-Compliant", variant: "default", className: "border-[var(--danger)]/25 bg-[var(--danger)]/10 text-[var(--danger)]" },
  success: { label: "Success", variant: "success" },
  denied: { label: "Denied", variant: "default", className: "border-[var(--danger)]/25 bg-[var(--danger)]/10 text-[var(--danger)]" },
  warning: { label: "Warning", variant: "warning" },
};

type OperationsBadgeProps = {
  variant: OperationsBadgeVariant;
  label?: string;
};

export function OperationsBadge({ variant, label }: OperationsBadgeProps) {
  const config = VARIANT_STYLES[variant];

  return (
    <Badge variant={config.variant} className={cn(config.className)}>
      {label ?? config.label}
    </Badge>
  );
}

export function healthStatusBadge(status: "healthy" | "degraded" | "critical" | "offline") {
  return <OperationsBadge variant={status} />;
}

export function priorityBadge(priority: "critical" | "high" | "medium" | "low") {
  const map = {
    critical: "critical_priority",
    high: "high_priority",
    medium: "medium_priority",
    low: "low_priority",
  } as const;
  return <OperationsBadge variant={map[priority]} />;
}

export function workOrderStatusBadge(status: "open" | "in_progress" | "scheduled" | "completed" | "overdue") {
  return <OperationsBadge variant={status} />;
}

export function complianceStatusBadge(status: "compliant" | "review" | "at_risk" | "non_compliant") {
  return <OperationsBadge variant={status} />;
}
