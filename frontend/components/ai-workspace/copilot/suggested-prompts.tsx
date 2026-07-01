"use client";

import type { SuggestedPrompt } from "@/types/ai-workspace";

type SuggestedPromptsProps = {
  prompts: SuggestedPrompt[];
  onSelect?: (prompt: string) => void;
};

export function SuggestedPrompts({ prompts, onSelect }: SuggestedPromptsProps) {
  return (
    <div className="space-y-3">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Suggested prompts
      </p>
      <div className="flex flex-wrap gap-2">
        {prompts.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect?.(item.prompt)}
            className="rounded-xl border border-border bg-[var(--surface-secondary)] px-3 py-2 text-left text-xs text-muted-foreground transition-industrial hover:border-[var(--accent-steel)]/25 hover:text-white"
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
