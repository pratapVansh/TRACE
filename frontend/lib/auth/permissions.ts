import {
  PERMISSIONS,
  SUPER_ADMIN_ROLE,
  USER_ROLES,
  type Permission,
  type UserRole,
} from "@/types/permissions";

const ALL_PERMISSIONS = Object.values(PERMISSIONS);

const ROLE_PERMISSIONS: Record<UserRole, readonly Permission[]> = {
  SuperAdmin: ALL_PERMISSIONS,
  Admin: ALL_PERMISSIONS,
  Engineer: [
    PERMISSIONS.DASHBOARD,
    PERMISSIONS.DOCUMENTS_READ,
    PERMISSIONS.DOCUMENTS_UPLOAD,
    PERMISSIONS.SEARCH,
    PERMISSIONS.COPILOT,
    PERMISSIONS.KNOWLEDGE_GRAPH,
    PERMISSIONS.AI_AGENTS,
    PERMISSIONS.ASSETS_READ,
    PERMISSIONS.ASSETS_WRITE,
    PERMISSIONS.MAINTENANCE,
    PERMISSIONS.COMPLIANCE,
    PERMISSIONS.SOP_LIBRARY,
  ],
  Operator: [
    PERMISSIONS.DASHBOARD,
    PERMISSIONS.DOCUMENTS_READ,
    PERMISSIONS.SEARCH,
    PERMISSIONS.MAINTENANCE,
    PERMISSIONS.COPILOT,
    PERMISSIONS.AI_AGENTS,
  ],
  Viewer: [
    PERMISSIONS.DASHBOARD,
    PERMISSIONS.DOCUMENTS_READ,
    PERMISSIONS.SEARCH,
  ],
};

export function isUserRole(value: string | null | undefined): value is UserRole {
  return USER_ROLES.includes(value as UserRole);
}

export function getPermissionsForRole(role: string | null | undefined): Permission[] {
  if (role === SUPER_ADMIN_ROLE) {
    return [...ALL_PERMISSIONS];
  }

  if (!isUserRole(role)) {
    return [];
  }

  return [...ROLE_PERMISSIONS[role]];
}

export function canAccess(
  role: string | null | undefined,
  permission: Permission,
): boolean {
  return getPermissionsForRole(role).includes(permission);
}

export function canAccessAny(
  role: string | null | undefined,
  permissions: Permission[],
): boolean {
  return permissions.some((permission) => canAccess(role, permission));
}

export function canAccessAll(
  role: string | null | undefined,
  permissions: Permission[],
): boolean {
  return permissions.every((permission) => canAccess(role, permission));
}

export { ROLE_PERMISSIONS };
