import { useMemo } from "react";

import { useAuth } from "@/hooks/use-auth";
import {
  canAccess,
  canAccessAll,
  canAccessAny,
  getPermissionsForRole,
} from "@/lib/auth/permissions";
import type { Permission } from "@/types/permissions";

export function usePermissions() {
  const { user } = useAuth();
  const role = user?.role ?? null;

  return useMemo(
    () => ({
      role,
      permissions: getPermissionsForRole(role),
      canAccess: (permission: Permission) => canAccess(role, permission),
      canAccessAny: (permissions: Permission[]) => canAccessAny(role, permissions),
      canAccessAll: (permissions: Permission[]) => canAccessAll(role, permissions),
    }),
    [role],
  );
}
