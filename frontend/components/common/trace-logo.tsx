import { cn } from "@/lib/utils";

type TraceLogoProps = {
  size?: "sm" | "md" | "lg";
  showWordmark?: boolean;
  className?: string;
};

const sizeMap = {
  sm: { box: "size-9 text-[10px]", word: "text-sm tracking-[0.28em]" },
  md: { box: "size-11 text-xs", word: "text-lg tracking-[0.32em]" },
  lg: { box: "size-16 text-sm", word: "text-2xl tracking-[0.36em]" },
};

export function TraceLogo({
  size = "md",
  showWordmark = true,
  className,
}: TraceLogoProps) {
  const sizes = sizeMap[size];

  return (
    <div className={cn("inline-flex items-center gap-3", className)}>
      <div
        className={cn(
          "flex shrink-0 items-center justify-center rounded-xl border border-[var(--accent-steel)]/30 bg-[var(--surface)] font-semibold text-foreground shadow-sm",
          sizes.box,
        )}
      >
        TR
      </div>
      {showWordmark ? (
        <span className={cn("font-semibold text-foreground", sizes.word)}>
          TRACE
        </span>
      ) : null}
    </div>
  );
}
