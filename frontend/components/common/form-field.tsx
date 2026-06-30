import type { ReactNode } from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";

import { cn } from "@/lib/utils";

type FormMessageProps = {
  variant: "error" | "success";
  children: ReactNode;
  className?: string;
};

export function FormMessage({ variant, children, className }: FormMessageProps) {
  const isError = variant === "error";

  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-xl border px-4 py-3 text-sm transition-opacity duration-200",
        isError
          ? "border-[var(--danger)]/30 bg-[var(--danger)]/10 text-[var(--danger)]"
          : "border-[var(--success)]/30 bg-[var(--success)]/10 text-[var(--success)]",
        className,
      )}
    >
      {isError ? (
        <AlertCircle className="mt-0.5 size-4 shrink-0" />
      ) : (
        <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
      )}
      <span className="leading-relaxed">{children}</span>
    </div>
  );
}

type FormFieldProps = {
  label: string;
  htmlFor: string;
  error?: string;
  children: ReactNode;
};

export function FormField({ label, htmlFor, error, children }: FormFieldProps) {
  return (
    <div className="space-y-2.5">
      <label
        htmlFor={htmlFor}
        className="block text-sm font-medium text-foreground/90"
      >
        {label}
      </label>
      {children}
      {error ? (
        <p className="flex items-center gap-1.5 text-sm text-[var(--danger)]">
          <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      ) : null}
    </div>
  );
}
