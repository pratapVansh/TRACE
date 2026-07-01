"use client";

import { ExecutiveDashboard } from "@/components/dashboard/executive-dashboard";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function DashboardPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.DASHBOARD}>
      <ExecutiveDashboard />
    </ProtectedPage>
  );
}
