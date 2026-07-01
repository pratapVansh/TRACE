import { Badge } from "@/components/ui/badge";

const STATUS_CONFIG = {
  active: { label: "Active", variant: "success" as const },
  inactive: { label: "Inactive", variant: "secondary" as const },
};

const ROLE_VARIANT: Record<
  string,
  "default" | "success" | "warning" | "secondary"
> = {
  SuperAdmin: "warning",
  Admin: "warning",
  Engineer: "default",
  Operator: "success",
  Viewer: "secondary",
};

export function UserStatusBadge({ isActive }: { isActive: boolean }) {
  const config = isActive ? STATUS_CONFIG.active : STATUS_CONFIG.inactive;
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

export function UserRoleBadge({ role }: { role: string }) {
  return <Badge variant={ROLE_VARIANT[role] ?? "secondary"}>{role}</Badge>;
}
