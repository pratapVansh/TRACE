"use client";

import { cn } from "@/lib/utils";
import type { SettingsField, SettingsSectionData } from "@/types/administration";

function SettingsFieldRow({ field }: { field: SettingsField }) {
  if (field.type === "toggle") {
    return (
      <div className="flex items-center justify-between gap-4 rounded-xl border border-border bg-[var(--surface-secondary)] px-4 py-3.5">
        <span className="text-sm text-foreground">{field.label}</span>
        <button
          type="button"
          disabled
          role="switch"
          aria-checked={field.enabled}
          className={cn(
            "relative h-6 w-11 shrink-0 rounded-full transition-colors",
            field.enabled ? "bg-[var(--accent-steel)]" : "bg-[var(--surface)]",
          )}
        >
          <span
            className={cn(
              "absolute top-0.5 size-5 rounded-full bg-white transition-transform",
              field.enabled ? "left-[22px]" : "left-0.5",
            )}
          />
        </button>
      </div>
    );
  }

  if (field.type === "select") {
    return (
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">{field.label}</label>
        <select
          disabled
          value={field.value}
          className="h-11 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-4 text-sm text-muted-foreground"
        >
          {field.options?.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground">{field.label}</label>
      <input
        type="text"
        readOnly
        value={field.value}
        className="h-11 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-4 text-sm text-muted-foreground"
      />
    </div>
  );
}

type SettingsSectionPanelProps = {
  section: SettingsSectionData;
};

export function SettingsSectionPanel({ section }: SettingsSectionPanelProps) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-xl font-semibold text-white">{section.title}</h3>
        <p className="mt-2 text-sm text-muted-foreground">{section.description}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {section.fields.map((field) => (
          <SettingsFieldRow key={field.id} field={field} />
        ))}
      </div>
    </div>
  );
}
