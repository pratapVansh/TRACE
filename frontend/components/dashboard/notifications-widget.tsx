import { Bell } from "lucide-react";

import { WidgetCard } from "@/components/dashboard/widget-card";
import { WidgetHeader } from "@/components/dashboard/widget-header";
import { Badge } from "@/components/ui/badge";
import { formatRelativeTime } from "@/lib/dashboard/format";
import { cn } from "@/lib/utils";
import type { DashboardNotification } from "@/types/dashboard";

const PRIORITY_VARIANT = {
  low: "secondary",
  medium: "default",
  high: "warning",
} as const;

type NotificationsWidgetProps = {
  notifications: DashboardNotification[];
};

export function NotificationsWidget({ notifications }: NotificationsWidgetProps) {
  const unreadCount = notifications.filter((item) => !item.read).length;

  return (
    <WidgetCard>
      <WidgetHeader
        sectionLabel="Alerts"
        title="Notifications"
        description="Operational alerts, compliance deadlines, and system updates."
        action={
          unreadCount > 0 ? (
            <Badge variant="warning">{unreadCount} unread</Badge>
          ) : (
            <Badge variant="success">All read</Badge>
          )
        }
      />

      <ul className="flex flex-1 flex-col gap-3">
        {notifications.map((notification) => (
          <li
            key={notification.id}
            className={cn(
              "rounded-md border p-4 transition-industrial",
              notification.read
                ? "border-border bg-[var(--surface-secondary)]"
                : "border-[var(--accent-steel)]/20 bg-[var(--surface-secondary)]",
            )}
          >
            <div className="flex items-start gap-3">
              <div
                className={cn(
                  "flex size-9 shrink-0 items-center justify-center rounded-lg border",
                  notification.read
                    ? "border-border bg-[var(--surface)] text-muted-foreground"
                    : "border-[var(--accent-steel)]/25 bg-[var(--surface)] text-[var(--accent-steel-muted)]",
                )}
              >
                <Bell className="size-4" strokeWidth={1.75} />
              </div>
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[12px] font-medium text-foreground">{notification.title}</p>
                  <Badge variant={PRIORITY_VARIANT[notification.priority]}>
                    {notification.priority}
                  </Badge>
                </div>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {notification.message}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatRelativeTime(notification.timestamp)}
                </p>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
