import type { ReactNode } from "react";

type WidgetHeaderProps = {
  sectionLabel: string;
  title: string;
  description?: string;
  action?: ReactNode;
};

export function WidgetHeader({
  sectionLabel,
  title,
  description,
  action,
}: WidgetHeaderProps) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-start sm:justify-between">
      <div className="space-y-2">
        <p className="section-label">{sectionLabel}</p>
        <h3 className="text-lg font-semibold text-white sm:text-xl">{title}</h3>
        {description ? (
          <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
