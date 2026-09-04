import { cn } from "@/lib/utils";

type MetricBarProps = {
  label: string;
  value: number;
  displayValue?: string;
  color?: string;
  showLabel?: boolean;
  className?: string;
};

export function MetricBar({
  label,
  value,
  displayValue,
  color = "var(--accent-steel)",
  showLabel = true,
  className,
}: MetricBarProps) {
  const clampedValue = Math.min(100, Math.max(0, value));

  return (
    <div className={cn("space-y-2", className)}>
      {showLabel ? (
        <div className="flex items-center justify-between gap-3 text-[12px]">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-medium text-foreground">{displayValue ?? `${value}%`}</span>
        </div>
      ) : (
        <div className="flex justify-end text-[12px]">
          <span className="font-medium text-foreground">{displayValue ?? `${value}%`}</span>
        </div>
      )}
      <div className="h-2 overflow-hidden rounded-full bg-[var(--surface-secondary)]">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${clampedValue}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}
