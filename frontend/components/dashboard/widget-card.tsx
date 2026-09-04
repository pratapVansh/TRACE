import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type WidgetCardProps = {
  children: ReactNode;
  className?: string;
};

export function WidgetCard({ children, className }: WidgetCardProps) {
  return (
    <section
      className={cn(
        "industrial-card flex h-full min-h-0 flex-col p-2.5 transition-industrial hover:border-[var(--accent-steel)]/25",
        className,
      )}
    >
      {children}
    </section>
  );
}
