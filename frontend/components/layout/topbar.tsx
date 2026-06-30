"use client";

import { Bell, LogOut, Menu, Search, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { AUTH_ROUTES } from "@/lib/auth/routes";

type TopbarProps = {
  onMenuClick?: () => void;
};

export function Topbar({ onMenuClick }: TopbarProps) {
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    router.replace(AUTH_ROUTES.login);
  };

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-[var(--sidebar)]/95 backdrop-blur-sm">
      <div className="flex h-16 items-center gap-4 px-4 sm:px-6 lg:px-8">
        <button
          type="button"
          aria-label="Open navigation"
          className="rounded-xl border border-border p-2 text-muted-foreground transition-industrial hover:bg-[var(--surface)] hover:text-white lg:hidden"
          onClick={onMenuClick}
        >
          <Menu className="size-5" />
        </button>

        <div className="hidden min-w-0 flex-1 md:block">
          <p className="section-label">Operations Console</p>
          <h1 className="truncate text-lg font-semibold text-white">
            Industrial Intelligence Dashboard
          </h1>
        </div>

        <div className="relative mx-auto hidden w-full max-w-md lg:block">
          <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            placeholder="Search documents, assets, tags…"
            disabled
            className="h-10 w-full rounded-xl border border-border bg-[var(--surface-secondary)] pr-4 pl-10 text-sm text-foreground placeholder:text-muted-foreground transition-industrial focus-visible:border-[var(--accent-steel)]/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-steel)]/10"
            aria-label="Search"
          />
        </div>

        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="size-10 rounded-xl text-muted-foreground hover:bg-[var(--surface)] hover:text-foreground"
            disabled
            aria-label="Notifications"
          >
            <Bell className="size-4.5" />
          </Button>

          <div className="hidden items-center gap-3 rounded-xl border border-border bg-[var(--surface)] px-3 py-2 sm:flex">
            <div className="flex size-9 items-center justify-center rounded-lg bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)]">
              <UserRound className="size-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-white">
                {user?.full_name}
              </p>
              <Badge variant="secondary" className="mt-1">
                {user?.role}
              </Badge>
            </div>
          </div>

          <Button
            variant="outline"
            onClick={handleLogout}
            className="h-10 rounded-xl border-border bg-transparent px-3 text-foreground transition-industrial hover:bg-[var(--surface)] sm:px-4"
          >
            <LogOut className="size-4" />
            <span className="hidden sm:inline">Sign out</span>
          </Button>
        </div>
      </div>
    </header>
  );
}
