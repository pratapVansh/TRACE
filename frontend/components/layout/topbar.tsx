"use client";

import { ChevronRight, LogOut, Menu, Search } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { useAuth } from "@/hooks/use-auth";
import { isNavItemActive, NAV_SECTIONS } from "@/lib/auth/navigation";
import { AUTH_ROUTES } from "@/lib/auth/routes";

type TopbarProps = {
  onMenuClick?: () => void;
};

/** Section and page names for the current route, from the nav config. */
function useBreadcrumb(pathname: string): { section: string; page: string } | null {
  for (const section of NAV_SECTIONS) {
    for (const item of section.items) {
      if (isNavItemActive(pathname, item.href)) {
        return { section: section.title, page: item.label };
      }
    }
  }
  return null;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const crumb = useBreadcrumb(pathname ?? "");

  const handleLogout = async () => {
    await logout();
    router.replace(AUTH_ROUTES.login);
  };

  return (
    <header className="sticky top-0 z-30 h-12 shrink-0 border-b border-border bg-[var(--sidebar)]/95 backdrop-blur-sm">
      <div className="flex h-12 items-center gap-2 px-3 lg:px-4">
        <button
          type="button"
          aria-label="Open navigation"
          className="rounded border border-border p-1 text-muted-foreground transition-industrial hover:bg-[var(--surface-secondary)] hover:text-foreground lg:hidden"
          onClick={onMenuClick}
        >
          <Menu className="size-4" />
        </button>

        {/* Where you are, not what the product is called. */}
        <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1">
          {crumb ? (
            <>
              <span className="hidden text-[11px] text-muted-foreground sm:inline">
                {crumb.section}
              </span>
              <ChevronRight
                className="hidden size-3 shrink-0 text-muted-foreground/40 sm:inline"
                strokeWidth={2}
              />
              <span className="truncate text-[12px] font-medium text-foreground">
                {crumb.page}
              </span>
            </>
          ) : null}
        </nav>

        <div className="relative mx-auto hidden w-full max-w-sm lg:block">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground/60" />
          <input
            type="search"
            placeholder="Search documents, assets, tags…"
            disabled
            className="h-7 w-full rounded border border-border bg-[var(--surface-secondary)] pr-3 pl-8 text-[12px] text-foreground placeholder:text-muted-foreground/70 transition-industrial focus-visible:border-[var(--accent-steel)]/40 focus-visible:outline-none disabled:opacity-60"
            aria-label="Search"
          />
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          <ThemeToggle />

          {user ? (
            <div className="hidden items-baseline gap-1.5 border-l border-border pl-2 sm:flex">
              <span className="max-w-[140px] truncate text-[12px] text-foreground">
                {user.full_name}
              </span>
              <span className="font-mono text-[10px] tracking-wide text-muted-foreground/70 uppercase">
                {user.role}
              </span>
            </div>
          ) : null}

          <button
            type="button"
            onClick={handleLogout}
            title="Sign out"
            className="inline-flex h-7 items-center gap-1.5 rounded border border-border bg-[var(--surface-secondary)] px-2 text-[11px] font-medium text-muted-foreground transition-industrial hover:border-[var(--danger)]/40 hover:text-[var(--danger)]"
          >
            <LogOut className="size-3.5" strokeWidth={1.75} />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </div>
    </header>
  );
}
