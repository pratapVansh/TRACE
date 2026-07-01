import { StatCard } from "@/components/operations/stat-card";
import { Network } from "lucide-react";

import type { GraphInfoItem, GraphStat } from "@/types/ai-workspace";

type GraphInfoPanelProps = {
  stats: GraphStat[];
  items: GraphInfoItem[];
};

export function GraphInfoPanel({ stats, items }: GraphInfoPanelProps) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        {stats.map((stat) => (
          <StatCard
            key={stat.label}
            label={stat.label}
            value={stat.value}
            icon={Network}
          />
        ))}
      </div>

      <div className="industrial-card p-5 sm:p-6">
        <p className="section-label">Schema</p>
        <h3 className="mt-1 text-lg font-semibold text-white">Information panel</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Relationship types that will be extracted and linked across the industrial knowledge base.
        </p>

        <ul className="mt-5 space-y-3">
          {items.map((item) => (
            <li
              key={item.id}
              className="rounded-xl border border-border bg-[var(--surface-secondary)] p-4"
            >
              <p className="text-sm font-medium text-white">{item.label}</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {item.description}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
