"use client";

import type { ReactNode } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { RoleGuard } from "@/components/auth/role-guard";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import type { Permission } from "@/types/permissions";

type ProtectedPageProps = {
  permission: Permission;
  children: ReactNode;
};

export function ProtectedPage({ permission, children }: ProtectedPageProps) {
  return (
    <AuthGuard>
      <RoleGuard permission={permission}>
        <DashboardLayout>{children}</DashboardLayout>
      </RoleGuard>
    </AuthGuard>
  );
}
