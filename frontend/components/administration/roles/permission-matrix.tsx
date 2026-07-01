import { Fragment } from "react";
import { Check, Minus } from "lucide-react";

import { ROLE_PERMISSIONS } from "@/lib/auth/permissions";
import {
  PERMISSION_GROUPS,
  PERMISSION_LABELS,
} from "@/lib/administration/constants";
import { USER_ROLES } from "@/types/permissions";
import type { Permission, UserRole } from "@/types/permissions";

function hasPermission(role: UserRole, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role].includes(permission);
}

export function PermissionMatrix() {
  return (
    <div className="industrial-card overflow-hidden">
      <div className="border-b border-border px-6 py-5">
        <p className="section-label">Access control</p>
        <h3 className="mt-1 text-lg font-semibold text-white">Permission matrix</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Role-to-permission mapping enforced by frontend navigation guards.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-[var(--surface-secondary)]/60">
              <th className="px-6 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Permission
              </th>
              {USER_ROLES.map((role) => (
                <th
                  key={role}
                  className="px-4 py-3.5 text-center text-xs font-medium tracking-wide text-muted-foreground uppercase last:pr-6"
                >
                  {role}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PERMISSION_GROUPS.map((group) => (
              <Fragment key={group.label}>
                <tr className="bg-[var(--surface-secondary)]/30">
                  <td
                    colSpan={USER_ROLES.length + 1}
                    className="px-6 py-2 text-xs font-medium tracking-wide text-[var(--accent-steel-muted)] uppercase"
                  >
                    {group.label}
                  </td>
                </tr>
                {group.permissions.map((permission) => (
                  <tr
                    key={permission}
                    className="border-b border-border/70 last:border-0 hover:bg-[var(--surface-secondary)]/40"
                  >
                    <td className="px-6 py-3.5 text-muted-foreground">
                      {PERMISSION_LABELS[permission]}
                    </td>
                    {USER_ROLES.map((role) => {
                      const allowed = hasPermission(role, permission);
                      return (
                        <td
                          key={`${permission}-${role}`}
                          className="px-4 py-3.5 text-center last:pr-6"
                        >
                          <span className="inline-flex size-7 items-center justify-center rounded-lg border border-border bg-[var(--surface-secondary)]">
                            {allowed ? (
                              <Check
                                className="size-3.5 text-[var(--success)]"
                                strokeWidth={2.5}
                              />
                            ) : (
                              <Minus
                                className="size-3.5 text-muted-foreground/50"
                                strokeWidth={2}
                              />
                            )}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
