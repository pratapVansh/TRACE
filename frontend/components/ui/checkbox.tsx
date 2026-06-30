import * as React from "react";

import { cn } from "@/lib/utils";

function Checkbox({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="checkbox"
      className={cn(
        "size-4 rounded border border-border bg-[var(--surface-secondary)] accent-[var(--accent-steel)] transition-industrial focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-steel)]/20",
        className,
      )}
      {...props}
    />
  );
}

export { Checkbox };
