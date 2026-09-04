import type { ReactNode } from "react";

type PageHeaderProps = {
  sectionLabel: string;
  title: string;
  description: string;
  action?: ReactNode;
};

/**
 * A console labels the screen you are on; it does not sell it. One line:
 * title, supporting text, and actions — no stacked hero block.
 */
export function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <header className="mb-3 flex items-baseline gap-3 border-b border-border pb-2">
      <h2 className="page-title shrink-0">{title}</h2>
      <p className="page-subtitle hidden min-w-0 flex-1 truncate md:block">
        {description}
      </p>
      {action ? <div className="ml-auto shrink-0">{action}</div> : null}
    </header>
  );
}
