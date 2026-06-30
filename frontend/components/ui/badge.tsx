import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-medium tracking-wide transition-colors duration-200",
  {
    variants: {
      variant: {
        default:
          "border-[var(--accent-steel)]/25 bg-[var(--accent-steel)]/10 text-[var(--accent-steel-muted)]",
        success:
          "border-[var(--success)]/25 bg-[var(--success)]/10 text-[var(--success)]",
        warning:
          "border-[var(--warning)]/25 bg-[var(--warning)]/10 text-[var(--warning)]",
        secondary:
          "border-border bg-[var(--surface-secondary)] text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> &
  VariantProps<typeof badgeVariants>) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
