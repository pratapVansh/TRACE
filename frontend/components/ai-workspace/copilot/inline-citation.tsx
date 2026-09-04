"use client";

import { cn } from "@/lib/utils";

type InlineCitationProps = {
  /** Zero-based index into the turn's citation array. */
  index: number;
  /** Literal text that produced the reference — a marker or a document name. */
  label: string;
  via: "marker" | "mention";
  documentName?: string;
  active?: boolean;
  onSelect?: (index: number) => void;
};

export function InlineCitation({
  index,
  label,
  via,
  documentName,
  active,
  onSelect,
}: InlineCitationProps) {
  const title = documentName
    ? `Source ${index + 1}: ${documentName}`
    : `Source ${index + 1}`;

  // A marker collapses to its number; a document name keeps its own text and
  // is underlined in place so the sentence still reads normally.
  if (via === "marker") {
    return (
      <button
        type="button"
        onClick={() => onSelect?.(index)}
        title={title}
        className={cn(
          "mx-px inline-flex h-[15px] min-w-[15px] translate-y-[-1px] items-center justify-center rounded-[3px] px-1 align-middle font-mono text-[10px] leading-none transition-industrial",
          active
            ? "bg-[var(--accent-steel)] text-white ring-1 ring-[var(--accent-steel)]"
            : "bg-[var(--accent-steel)]/18 text-[var(--accent-steel-muted)] hover:bg-[var(--accent-steel)]/35 hover:text-foreground",
        )}
      >
        {index + 1}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={() => onSelect?.(index)}
      title={title}
      className={cn(
        "inline underline decoration-dotted underline-offset-2 transition-industrial",
        active
          ? "text-foreground decoration-[var(--accent-steel)]"
          : "text-[var(--accent-steel-muted)] decoration-[var(--accent-steel)]/50 hover:text-foreground hover:decoration-[var(--accent-steel)]",
      )}
    >
      {label}
      <span className="ml-0.5 align-super font-mono text-[9px] text-[var(--accent-steel)]">
        {index + 1}
      </span>
    </button>
  );
}
