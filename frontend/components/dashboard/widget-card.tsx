import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type WidgetCardProps = {
  children: ReactNode;
  className?: string;
};

export function WidgetCard({ children, className }: WidgetCardProps) {
  return (
    <section className={cn("industrial-card flex h-full flex-col p-6 sm:p-7", className)}>
      {children}
    </section>
  );
}
