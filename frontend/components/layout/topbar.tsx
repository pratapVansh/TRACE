"use client";

import { LogOut, Menu, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/use-auth";
import { useTheme } from "@/contexts/theme-context";
import { AUTH_ROUTES } from "@/lib/auth/routes";

type TopbarProps = {
  onMenuClick?: () => void;
};

export function Topbar({ onMenuClick }: TopbarProps) {
  const router = useRouter();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const handleLogout = async () => {
    await logout();
    router.replace(AUTH_ROUTES.login);
  };

  const initials = user?.full_name
    ? user.full_name.split(" ").map((n: string) => n[0]).join("").toUpperCase().slice(0, 2)
    : "U";

  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-[var(--bg)]/80 backdrop-blur-md">
      <div className="flex h-14 items-center gap-3 px-4 sm:px-6">
        <button
          type="button"
          aria-label="Open navigation"
          className="flex size-8 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] lg:hidden"
          onClick={onMenuClick}
        >
          <Menu className="size-4" />
        </button>

        <Link href="/dashboard" className="flex items-center gap-2 lg:hidden">
          <div className="flex size-6 items-center justify-center rounded-md bg-[var(--accent)] text-white text-[10px] font-bold">
            T
          </div>
          <span className="text-sm font-semibold tracking-tight">TRACE</span>
        </Link>

        <div className="ml-auto flex items-center gap-2">
          <div className="flex items-center gap-2.5 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-1.5">
            <div className="flex size-7 items-center justify-center rounded-md bg-[var(--accent-muted)] text-[var(--accent)] text-xs font-semibold">
              {initials}
            </div>
            <div className="hidden min-w-0 sm:block">
              <p className="truncate text-sm font-medium leading-tight">
                {user?.full_name}
              </p>
              <p className="text-[11px] leading-tight text-[var(--text-muted)]">
                {user?.role}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={toggleTheme}
            className="flex size-8 items-center justify-center rounded-lg text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>

          <button
            type="button"
            onClick={handleLogout}
            className="flex size-8 items-center justify-center rounded-lg text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
            aria-label="Sign out"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
