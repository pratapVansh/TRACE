"use client";

import {
  Building2,
  Database,
  Palette,
  Bell,
  Bot,
  Shield,
} from "lucide-react";
import { useState } from "react";

import { SettingsSectionPanel } from "@/components/administration/settings/settings-section-panel";
import { PageHeader } from "@/components/common/page-header";
import { SYSTEM_SETTINGS } from "@/lib/administration/mock-data";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

const SECTION_ICONS: Record<string, LucideIcon> = {
  company: Building2,
  security: Shield,
  notifications: Bell,
  ai: Bot,
  database: Database,
  appearance: Palette,
};

export function SystemSettingsPageContent() {
  const [activeSection, setActiveSection] = useState<string | undefined>(undefined);
  const current = SYSTEM_SETTINGS.find((s) => s.id === activeSection);

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="Administration"
        title="System Settings"
        description="Configure organization profile, security policies, notifications, AI defaults, and platform appearance."
      />

      {SYSTEM_SETTINGS.length === 0 ? (
        <div className="rounded-xl border border-border bg-[var(--surface-secondary)] p-8 text-center">
          <p className="text-sm text-muted-foreground">No settings available.</p>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
          <nav className="industrial-card p-3">
            <ul className="space-y-1">
              {SYSTEM_SETTINGS.map((section) => {
                const Icon = SECTION_ICONS[section.id] ?? Building2;
                const isActive = section.id === activeSection;

                return (
                  <li key={section.id}>
                    <button
                      type="button"
                      onClick={() => setActiveSection(section.id)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-industrial",
                        isActive
                          ? "border border-[var(--accent-steel)]/25 bg-[var(--surface-secondary)] text-white"
                          : "text-muted-foreground hover:bg-[var(--surface-secondary)]/70 hover:text-foreground",
                      )}
                    >
                      <Icon className="size-4 shrink-0" strokeWidth={1.75} />
                      {section.title}
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="industrial-card p-6 sm:p-8">
            {current ? (
              <SettingsSectionPanel section={current} />
            ) : (
              <p className="text-sm text-muted-foreground">Select a settings section.</p>
            )}
            <p className="mt-8 border-t border-border pt-5 text-xs text-muted-foreground">
              Settings are read-only in this milestone. Backend persistence will be added in a
              future release.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
