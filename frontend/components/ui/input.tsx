"use client";

import { Input } from "@base-ui/react/input";
import * as React from "react";

import { cn } from "@/lib/utils";

function TextInput({
  className,
  ...props
}: React.ComponentProps<typeof Input>) {
  return (
    <Input
      className={cn(
        "flex h-12 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-4 text-sm text-foreground shadow-sm transition-industrial placeholder:text-muted-foreground hover:border-[var(--accent-steel)]/20 focus-visible:border-[var(--accent-steel)]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-steel)]/15 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export { TextInput as Input };
