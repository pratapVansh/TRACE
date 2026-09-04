import {
  ClipboardList,
  FileText,
  Search,
  Settings,
  ShieldCheck,
} from "lucide-react";

import { WidgetCard } from "@/components/dashboard/widget-card";
import { WidgetHeader } from "@/components/dashboard/widget-header";
import { formatRelativeTime } from "@/lib/dashboard/format";
import { cn } from "@/lib/utils";
import type { ActivityItem } from "@/types/dashboard";
import type { LucideIcon } from "lucide-react";

const ACTIVITY_ICONS: Record<ActivityItem["type"], LucideIcon> = {
  document: FileText,
  maintenance: ClipboardList,
  compliance: ShieldCheck,
  search: Search,
  system: Settings,
};

const ACTIVITY_COLORS: Record<ActivityItem["type"], string> = {
  document: "text-[var(--accent-steel-muted)]",
  maintenance: "text-[var(--warning)]",
  compliance: "text-[var(--success)]",
  search: "text-[var(--accent-steel)]",
  system: "text-muted-foreground",
};

type RecentActivityWidgetProps = {
  activities: ActivityItem[];
};

export function RecentActivityWidget({ activities }: RecentActivityWidgetProps) {
  return (
    <WidgetCard>
      <WidgetHeader
        sectionLabel="Operations Feed"
        title="Recent Activity"
        description="Cross-functional events across documents, maintenance, and compliance."
      />

      <ul className="relative flex flex-1 flex-col gap-0">
        {activities.map((activity, index) => {
          const Icon = ACTIVITY_ICONS[activity.type];

          return (
            <li key={activity.id} className="relative flex gap-4 pb-5 last:pb-0">
              {index < activities.length - 1 ? (
                <span
                  aria-hidden
                  className="absolute top-10 left-5 h-[calc(100%-1.25rem)] w-px bg-border"
                />
              ) : null}

              <div
                className={cn(
                  "relative z-10 flex size-7 shrink-0 items-center justify-center rounded-lg border border-border bg-[var(--surface-secondary)]",
                  ACTIVITY_COLORS[activity.type],
                )}
              >
                <Icon className="size-4" strokeWidth={1.75} />
              </div>

              <div className="min-w-0 flex-1 space-y-1 pt-0.5">
                <p className="text-[12px] text-foreground">
                  <span className="font-medium">{activity.action}</span>
                  {" — "}
                  <span className="text-muted-foreground">{activity.subject}</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  {activity.actor} · {formatRelativeTime(activity.timestamp)}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    </WidgetCard>
  );
}
