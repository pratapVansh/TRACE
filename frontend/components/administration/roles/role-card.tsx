import { Shield, Users } from "lucide-react";

import { UserRoleBadge } from "@/components/administration/user-badges";
import type { RoleDefinition } from "@/types/administration";

type RoleCardProps = {
  role: RoleDefinition;
};

export function RoleCard({ role }: RoleCardProps) {
  return (
    <article className="industrial-card p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="flex size-11 items-center justify-center rounded-xl border border-border bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)]">
          <Shield className="size-5" strokeWidth={1.75} />
        </div>
        <UserRoleBadge role={role.role} />
      </div>

      <h3 className="mt-5 text-lg font-semibold text-white">{role.role}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        {role.description}
      </p>

      <div className="mt-5 flex items-center gap-2 border-t border-border pt-5 text-sm text-muted-foreground">
        <Users className="size-4" />
        <span>
          {role.userCount} user{role.userCount === 1 ? "" : "s"}
        </span>
      </div>
    </article>
  );
}
