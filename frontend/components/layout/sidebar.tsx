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
          className="fixed inset-0 z-40 bg-black/50 transition-opacity duration-200 lg:hidden"
          onClick={onClose}
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 shrink-0 flex-col border-r border-border bg-[var(--sidebar)] transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-5">
          <TraceLogo size="sm" />
          <button
            type="button"
            aria-label="Close menu"
            className="rounded-lg p-2 text-muted-foreground transition-industrial hover:bg-[var(--surface)] hover:text-white lg:hidden"
            onClick={onClose}
          >
            <X className="size-4" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-4 py-6">
          {visibleSections.map((section) => (
            <div key={section.title} className="mb-8 last:mb-0">
              <p className="mb-3 px-3 text-[11px] font-medium tracking-[0.16em] text-muted-foreground uppercase">
                {section.title}
              </p>
              <ul className="space-y-1">
                {section.items.map(({ href, label, icon: Icon }) => {
                  const isActive = isNavItemActive(pathname, href);

                  return (
                    <li key={href}>
                      <Link
                        href={href}
                        onClick={onClose}
                        className={cn(
                          "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-industrial",
                          isActive
                            ? "border border-[var(--accent-steel)]/25 bg-[var(--surface)] text-white shadow-sm"
                            : "text-muted-foreground hover:bg-[var(--surface)]/70 hover:text-foreground",
                        )}
                      >
                        <Icon className="size-4 shrink-0" strokeWidth={1.75} />
                        <span>{label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-border px-5 py-5">
          <p className="text-xs leading-relaxed text-muted-foreground">
            Industrial knowledge intelligence for critical asset operations.
          </p>
        </div>
      </aside>
    </>
  );
}
