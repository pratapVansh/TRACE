"use client";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

interface AuthLoadingScreenProps {
  label?: string;
}

export function AuthLoadingScreen({
  label = "Initializing secure session",
}: AuthLoadingScreenProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background px-6">
      <div className="w-full max-w-md space-y-8">
        <div className="flex items-center gap-3">
          <Skeleton className="size-11 rounded-xl" />
          <Skeleton className="h-5 w-24" />
        </div>

        <div className="industrial-card space-y-6 p-8">
          <div className="space-y-3">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-8 w-56" />
            <Skeleton className="h-4 w-full" />
          </div>
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-12 w-full rounded-xl" />
        </div>

        <p className="text-center text-sm text-muted-foreground">{label}…</p>
      </div>
    </div>
  );
}

export function InlineLoading({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block size-4 animate-pulse rounded-full bg-current/30",
        className,
      )}
      aria-hidden="true"
    />
  );
}
