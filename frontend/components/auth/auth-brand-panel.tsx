"use client";

import {
  BarChart3,
  ClipboardCheck,
  Factory,
  FileStack,
  ShieldCheck,
} from "lucide-react";

import { TraceLogo } from "@/components/common/trace-logo";

const FEATURES = [
  {
    icon: Factory,
    title: "Asset-centric operations",
    description:
      "Unify equipment tags, maintenance history, and technical documentation across facilities.",
  },
  {
    icon: FileStack,
    title: "Technical records management",
    description:
      "Drawings, SOPs, inspection reports, and OEM manuals in one governed repository.",
  },
  {
    icon: ShieldCheck,
    title: "Compliance & audit readiness",
    description:
      "Role-based access and traceability designed for regulated industrial environments.",
  },
  {
    icon: BarChart3,
    title: "Operational intelligence",
    description:
      "Executive visibility into document coverage, asset health, and maintenance workload.",
  },
  {
    icon: ClipboardCheck,
    title: "Plant-wide standardization",
    description:
      "Consistent workflows for engineers, operators, and reliability teams enterprise-wide.",
  },
] as const;

function GeometricBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="absolute -top-20 -left-16 size-64 rounded-full border border-white/[0.04]" />
      <div className="absolute top-1/3 -right-24 size-80 rounded-full border border-white/[0.03]" />
      <div className="absolute bottom-24 left-1/4 h-px w-72 rotate-12 bg-[var(--surface)]/[0.06]" />
      <div className="absolute top-1/2 right-1/3 size-32 rotate-45 border border-white/[0.04]" />
      <div className="absolute right-16 bottom-16 h-40 w-px bg-[var(--surface)]/[0.05]" />
    </div>
  );
}

export function AuthBrandPanel() {
  return (
    <div className="relative flex h-full min-h-[320px] flex-col justify-between overflow-hidden border-r border-border bg-[var(--sidebar)] px-8 py-10 lg:min-h-screen lg:px-12 lg:py-14 xl:px-16">
      <GeometricBackdrop />

      <div className="relative flex flex-col gap-10 lg:gap-12">
        <TraceLogo size="lg" />

        <div className="max-w-xl space-y-4">
          <p className="section-label">Industrial Knowledge Intelligence</p>
          <h1 className="text-3xl leading-[1.15] font-semibold text-foreground xl:text-[2.75rem]">
            Technical Records &amp; Asset Compliance Engine
          </h1>
          <p className="max-w-lg text-base leading-relaxed text-muted-foreground">
            Enterprise software for manufacturing, energy, and heavy-asset
            organizations — built for engineers, plant managers, and compliance
            leaders.
          </p>
        </div>

        <ul className="grid gap-3">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <li
              key={title}
              className="rounded-xl border border-border bg-[var(--surface)]/80 p-4 transition-industrial hover:border-[var(--accent-steel)]/20 hover:bg-[var(--surface)]"
            >
              <div className="flex items-start gap-4">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)]">
                  <Icon className="size-4.5" strokeWidth={1.75} />
                </div>
                <div className="space-y-1">
                  <h2 className="text-sm font-medium text-foreground">{title}</h2>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {description}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <p className="relative mt-10 text-xs tracking-[0.16em] text-muted-foreground uppercase">
        Trusted by industrial operations teams worldwide
      </p>
    </div>
  );
}
