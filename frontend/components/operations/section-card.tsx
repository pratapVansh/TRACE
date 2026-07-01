import type { ReactNode } from "react";

type SectionCardProps = {
  sectionLabel: string;
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
};

export function SectionCard({
  sectionLabel,
  title,
  description,
  action,
  children,
}: SectionCardProps) {
  return (
    <section className="industrial-card p-5 sm:p-6">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <p className="section-label">{sectionLabel}</p>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          {description ? (
            <p className="text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}
