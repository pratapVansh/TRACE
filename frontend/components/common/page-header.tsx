import type { ReactNode } from "react";

type PageHeaderProps = {
  sectionLabel: string;
  title: string;
  description: string;
  action?: ReactNode;
};

export function PageHeader({
  sectionLabel,
  title,
  description,
  action,
}: PageHeaderProps) {
  return (
    <section className="space-y-4">
      <p className="section-label">{sectionLabel}</p>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-3">
          <h2 className="page-title">{title}</h2>
          <p className="page-subtitle max-w-2xl">{description}</p>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </section>
  );
}
