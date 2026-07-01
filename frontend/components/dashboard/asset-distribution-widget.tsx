import { MetricBar } from "@/components/dashboard/metric-bar";
import { WidgetCard } from "@/components/dashboard/widget-card";
import { WidgetHeader } from "@/components/dashboard/widget-header";
import type { AssetCategory } from "@/types/dashboard";

type AssetDistributionWidgetProps = {
  categories: AssetCategory[];
  totalAssets: number;
};

export function AssetDistributionWidget({
  categories,
  totalAssets,
}: AssetDistributionWidgetProps) {
  return (
    <WidgetCard>
      <WidgetHeader
        sectionLabel="Asset Intelligence"
        title="Asset Distribution"
        description={`Equipment breakdown across ${totalAssets.toLocaleString()} registered industrial assets.`}
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {categories.slice(0, 3).map((category) => (
          <div
            key={category.id}
            className="rounded-xl border border-border bg-[var(--surface-secondary)] p-4"
          >
            <p className="text-xs text-muted-foreground">{category.label}</p>
            <p className="mt-2 text-2xl font-semibold text-white">
              {category.count.toLocaleString()}
            </p>
            <p className="mt-1 text-xs text-[var(--accent-steel-muted)]">
              {category.percentage}%
            </p>
          </div>
        ))}
      </div>

      <div className="flex flex-1 flex-col gap-4">
        {categories.map((category) => (
          <MetricBar
            key={category.id}
            label={category.label}
            value={category.percentage}
            displayValue={`${category.count.toLocaleString()} (${category.percentage}%)`}
            color={category.color}
          />
        ))}
      </div>
    </WidgetCard>
  );
}
