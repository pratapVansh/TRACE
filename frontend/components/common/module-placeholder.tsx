import type { ReactNode } from "react";

type ModulePlaceholderProps = {
  sectionLabel: string;
  title: string;
  description: string;
  children?: ReactNode;
};

export function ModulePlaceholder({
  sectionLabel,
  title,
  description,
  children,
}: ModulePlaceholderProps) {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 lg:gap-10">
      <section className="space-y-4">
        <p className="section-label">{sectionLabel}</p>
        <div className="space-y-3">
          <h2 className="page-title">{title}</h2>
          <p className="page-subtitle max-w-2xl">{description}</p>
        </div>
      </section>

      <section className="industrial-card p-6 sm:p-8">
        <p className="text-sm leading-relaxed text-muted-foreground">
          This module is part of the Milestone 3+ roadmap. Navigation and access
          control are active; feature content will be implemented in upcoming
          milestones.
        </p>
        {children}
      </section>
    </div>
  );
}
