"use client";

import type { ReactNode } from "react";
import { X } from "lucide-react";

type AdminDialogProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  description: string;
  children: ReactNode;
  footer?: ReactNode;
};

export function AdminDialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
}: AdminDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog backdrop"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <div className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto industrial-card p-6 sm:p-8">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <p className="section-label">Administration</p>
            <h3 className="mt-1 text-xl font-semibold text-white">{title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-muted-foreground hover:bg-[var(--surface-secondary)] hover:text-white"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        {children}

        {footer ? <div className="mt-6 flex gap-3">{footer}</div> : null}
      </div>
    </div>
  );
}
