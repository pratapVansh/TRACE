import type { ReactNode } from "react";

type WidgetHeaderProps = {
  sectionLabel: string;
  title: string;
  description?: string;
  action?: ReactNode;
};

/**
 * One rule-separated line. The stacked label/title/description block was three
 * lines of chrome above every widget; in a console the title carries it, and
 * `description` is kept as the accessible name rather than printed.
 */
export function WidgetHeader({ title, description, action }: WidgetHeaderProps) {
  return (
    <div className="mb-2 flex h-5 shrink-0 items-center justify-between gap-2 border-b border-border pb-1.5">
      <h3 className="section-label truncate" title={description ?? undefined}>
        {title}
      </h3>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
