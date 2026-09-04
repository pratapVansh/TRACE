import { PERMISSIONS, USER_ROLES, type Permission } from "@/types/permissions";

export const PERMISSION_LABELS: Record<Permission, string> = {
  [PERMISSIONS.DASHBOARD]: "Dashboard",
  [PERMISSIONS.DOCUMENTS_READ]: "Documents",
  [PERMISSIONS.DOCUMENTS_UPLOAD]: "Upload Documents",
  [PERMISSIONS.SEARCH]: "Search",
  [PERMISSIONS.COPILOT]: "Copilot",
  [PERMISSIONS.KNOWLEDGE_GRAPH]: "Knowledge Graph",
  [PERMISSIONS.ASSETS_READ]: "Assets",
  [PERMISSIONS.ASSETS_WRITE]: "Assets (Write)",
  [PERMISSIONS.MAINTENANCE]: "Maintenance",
  [PERMISSIONS.COMPLIANCE]: "Compliance",
  [PERMISSIONS.SOP_LIBRARY]: "SOP Library",
  [PERMISSIONS.USER_MANAGEMENT]: "User Management",
  [PERMISSIONS.ROLE_MANAGEMENT]: "Role Management",
  [PERMISSIONS.SYSTEM_SETTINGS]: "System Settings",
};

export const PERMISSION_GROUPS: { label: string; permissions: Permission[] }[] = [
  {
    label: "Platform",
    permissions: [
      PERMISSIONS.DASHBOARD,
      PERMISSIONS.USER_MANAGEMENT,
      PERMISSIONS.ROLE_MANAGEMENT,
      PERMISSIONS.SYSTEM_SETTINGS,
    ],
  },
  {
    label: "Knowledge",
    permissions: [
      PERMISSIONS.DOCUMENTS_READ,
      PERMISSIONS.DOCUMENTS_UPLOAD,
      PERMISSIONS.SEARCH,
      PERMISSIONS.SOP_LIBRARY,
    ],
  },
  {
    label: "Operations",
    permissions: [
      PERMISSIONS.ASSETS_READ,
      PERMISSIONS.ASSETS_WRITE,
      PERMISSIONS.MAINTENANCE,
      PERMISSIONS.COMPLIANCE,
    ],
  },
  {
    label: "Intelligence",
    permissions: [
      PERMISSIONS.COPILOT,
      PERMISSIONS.KNOWLEDGE_GRAPH,
    ],
  },
];

export const ROLE_DESCRIPTIONS: Record<string, string> = {
  SuperAdmin: "Organization owner with unrestricted platform access.",
  Admin: "Full system access, user management, and platform configuration.",
  Engineer: "Engineering documentation, assets, maintenance, compliance, and AI tools.",
  Operator: "Day-to-day operations, documents, search, maintenance, and Copilot access.",
  Viewer: "Read-only access to documents and search results.",
};

export const USER_STATUSES = ["all", "active", "inactive"] as const;

export const ALL_ROLES_FILTER = ["all", ...USER_ROLES] as const;

export { USER_ROLES };
