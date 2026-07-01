import { PERMISSIONS, USER_ROLES, type Permission } from "@/types/permissions";

export const PERMISSION_LABELS: Record<Permission, string> = {
  [PERMISSIONS.DASHBOARD]: "Dashboard",
  [PERMISSIONS.DOCUMENTS]: "Documents",
  [PERMISSIONS.DOCUMENTS_UPLOAD]: "Upload Documents",
  [PERMISSIONS.SEARCH]: "Search",
  [PERMISSIONS.ASSETS]: "Assets",
  [PERMISSIONS.MAINTENANCE]: "Maintenance",
  [PERMISSIONS.COMPLIANCE]: "Compliance",
  [PERMISSIONS.SOP_LIBRARY]: "SOP Library",
  [PERMISSIONS.COPILOT]: "Copilot",
  [PERMISSIONS.KNOWLEDGE_GRAPH]: "Knowledge Graph",
  [PERMISSIONS.AI_AGENTS]: "AI Agents",
  [PERMISSIONS.SETTINGS]: "Administration",
};

export const PERMISSION_GROUPS: { label: string; permissions: Permission[] }[] = [
  {
    label: "Platform",
    permissions: [PERMISSIONS.DASHBOARD, PERMISSIONS.SETTINGS],
  },
  {
    label: "Knowledge",
    permissions: [
      PERMISSIONS.DOCUMENTS,
      PERMISSIONS.DOCUMENTS_UPLOAD,
      PERMISSIONS.SEARCH,
      PERMISSIONS.SOP_LIBRARY,
    ],
  },
  {
    label: "Operations",
    permissions: [PERMISSIONS.ASSETS, PERMISSIONS.MAINTENANCE, PERMISSIONS.COMPLIANCE],
  },
  {
    label: "Intelligence",
    permissions: [
      PERMISSIONS.COPILOT,
      PERMISSIONS.KNOWLEDGE_GRAPH,
      PERMISSIONS.AI_AGENTS,
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
