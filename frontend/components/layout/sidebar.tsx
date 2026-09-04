"use client";

import { X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { TraceLogo } from "@/components/common/trace-logo";
import { usePermissions } from "@/hooks/use-permissions";
import { isNavItemActive, NAV_SECTIONS } from "@/lib/auth/navigation";
import { cn } from "@/lib/utils";

type SidebarProps = {
  mobileOpen?: boolean;
  onClose?: () => void;
};

export function Sidebar({ mobileOpen = false, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { canAccess } = usePermissions();

  const visibleSections = NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => canAccess(item.permission)),
  })).filter((section) => section.items.length > 0);

  return (
    <>
      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-black/50 transition-opacity duration-150 lg:hidden"
          onClick={onClose}
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-56 shrink-0 flex-col border-r border-border bg-[var(--sidebar)] transition-transform duration-150 lg:static lg:z-auto lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-border px-3">
          <TraceLogo size="sm" />
          <button
            type="button"
            aria-label="Close menu"
            className="rounded p-1 text-muted-foreground transition-industrial hover:bg-[var(--surface-secondary)] hover:text-foreground lg:hidden"
            onClick={onClose}
          >
            <X className="size-3.5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-2">
          {visibleSections.map((section) => (
            <div key={section.title} className="mb-3 last:mb-0">
              <p className="section-label mb-1 px-2">{section.title}</p>
              <ul>
                {section.items.map(({ href, label, icon: Icon }) => {
                  const isActive = isNavItemActive(pathname, href);

                  return (
                    <li key={href}>
                      <Link
                        href={href}
                        onClick={onClose}
                        aria-current={isActive ? "page" : undefined}
                        className={cn(
                          "relative flex h-7 items-center gap-2 rounded px-2 text-[12px] transition-industrial",
                          isActive
                            ? "bg-[var(--surface-secondary)] font-medium text-foreground"
                            : "text-muted-foreground hover:bg-[var(--surface-secondary)]/60 hover:text-foreground",
                        )}
                      >
                        {/* Active marker as a rule, not a filled pill. */}
                        <span
                          aria-hidden
                          className={cn(
                            "absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-full transition-industrial",
                            isActive ? "bg-[var(--accent-steel)]" : "bg-transparent",
                          )}
                        />
                        <Icon
                          className={cn(
                            "size-3.5 shrink-0",
                            isActive
                              ? "text-[var(--accent-steel)]"
                              : "text-muted-foreground/70",
                          )}
                          strokeWidth={1.75}
                        />
                        <span className="truncate">{label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="shrink-0 border-t border-border px-3 py-2">
          <p className="font-mono text-[10px] text-muted-foreground/60">
            TRACE · knowledge intelligence
          </p>
        </div>
      </aside>
    </>
  );
}
