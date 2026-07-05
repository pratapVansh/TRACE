import { AlertCircle, Info } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ValidationMessage } from "@/types/knowledge";

type ValidationMessagesProps = {
  messages: ValidationMessage[];
};

const ICONS = {
  error: AlertCircle,
  warning: AlertCircle,
  info: Info,
};

const STYLES = {
  error:
    "border-[var(--danger)]/30 bg-[var(--danger)]/10 text-[var(--danger)]",
  warning:
    "border-[var(--warning)]/30 bg-[var(--warning)]/10 text-[var(--warning)]",
  info: "border-[var(--accent-steel)]/30 bg-[var(--accent-steel)]/10 text-[var(--accent-steel-muted)]",
};

export function ValidationMessages({ messages }: ValidationMessagesProps) {
  if (messages.length === 0) return null;

  return (
    <ul className="space-y-2">
      {messages.map((message) => {
        const Icon = ICONS[message.type];

        return (
          <li
            key={message.id}
            className={cn(
              "flex items-start gap-3 rounded-xl border px-4 py-3 text-sm",
              STYLES[message.type],
            )}
          >
            <Icon className="mt-0.5 size-4 shrink-0" />
            <span>{message.message}</span>
          </li>
        );
      })}
    </ul>
  );
}
