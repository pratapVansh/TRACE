import { SUPER_ADMIN_ROLE } from "@/types/permissions";

export const ADMIN_ROLE = "Admin";

const ADMIN_MANAGED_ROLES = new Set(["Engineer", "Operator", "Viewer"]);

const SUPER_ADMIN_CREATABLE_ROLES = new Set([
  SUPER_ADMIN_ROLE,
  ADMIN_ROLE,
  "Engineer",
  "Operator",
  "Viewer",
]);

const ADMIN_CREATABLE_ROLES = ADMIN_MANAGED_ROLES;

export function filterVisibleUsers<T extends { role: string }>(
  users: T[],
  actorRole: string,
): T[] {
  if (actorRole === SUPER_ADMIN_ROLE) {
    return users;
  }

  if (actorRole === ADMIN_ROLE) {
    return users.filter((user) => user.role !== SUPER_ADMIN_ROLE);
  }

  return [];
}

export function canManageUser(actorRole: string, targetRole: string): boolean {
  if (actorRole === SUPER_ADMIN_ROLE) {
    return true;
  }

  if (actorRole === ADMIN_ROLE) {
    return ADMIN_MANAGED_ROLES.has(targetRole);
  }

  return false;
}

export function getCreatableRoles(actorRole: string): string[] {
  if (actorRole === SUPER_ADMIN_ROLE) {
    return [...SUPER_ADMIN_CREATABLE_ROLES];
  }

  if (actorRole === ADMIN_ROLE) {
    return [...ADMIN_CREATABLE_ROLES];
  }

  return [];
}

export function canAssignRole(actorRole: string, role: string): boolean {
  return getCreatableRoles(actorRole).includes(role);
}
