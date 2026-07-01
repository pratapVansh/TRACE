import Link from "next/link";

import { WidgetCard } from "@/components/dashboard/widget-card";
import { WidgetHeader } from "@/components/dashboard/widget-header";
import type { QuickAction } from "@/types/dashboard";

type QuickActionsWidgetProps = {
  actions: QuickAction[];
};

export function QuickActionsWidget({ actions }: QuickActionsWidgetProps) {
  return (
    <WidgetCard>
      <WidgetHeader
        sectionLabel="Shortcuts"
        title="Quick Actions"
        description="Jump to high-frequency operational workflows."
      />

      <ul className="grid flex-1 gap-3 sm:grid-cols-2 xl:grid-cols-1">
        {actions.map((action) => {
          const Icon = action.icon;

          return (
            <li key={action.id}>
              <Link
                href={action.href}
                className="group flex items-center gap-4 rounded-xl border border-border bg-[var(--surface-secondary)] p-4 transition-industrial hover:border-[var(--accent-steel)]/25 hover:bg-[var(--surface)]"
              >
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-[var(--surface)] text-[var(--accent-steel-muted)] transition-industrial group-hover:border-[var(--accent-steel)]/25">
                  <Icon className="size-4.5" strokeWidth={1.75} />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white">{action.label}</p>
                  <p className="text-xs text-muted-foreground">{action.description}</p>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </WidgetCard>
  );
}
