"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { usePermissions } from "@/hooks/use-permissions";
import { AUTH_ROUTES } from "@/lib/auth/routes";
import type { Permission } from "@/types/permissions";

type RoleGuardProps = {
  permission: Permission;
  children: ReactNode;
};

export function RoleGuard({ permission, children }: RoleGuardProps) {
  const router = useRouter();
  const { canAccess } = usePermissions();
  const allowed = canAccess(permission);

  useEffect(() => {
    if (!allowed) {
      router.replace(AUTH_ROUTES.accessDenied);
    }
  }, [allowed, router]);

  if (!allowed) {
    return <AuthLoadingScreen label="Checking access permissions" />;
  }

  return <>{children}</>;
}
