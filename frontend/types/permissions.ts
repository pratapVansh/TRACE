export const SUPER_ADMIN_ROLE = "SuperAdmin";

export const USER_ROLES = [
  "SuperAdmin",
  "Admin",
  "Engineer",
  "Operator",
  "Viewer",
] as const;

export type UserRole = (typeof USER_ROLES)[number];

export const PERMISSIONS = {
  DASHBOARD: "dashboard",
  DOCUMENTS_READ: "documents_read",
  DOCUMENTS_UPLOAD: "documents_upload",
  SEARCH: "search",
  COPILOT: "copilot",
  KNOWLEDGE_GRAPH: "knowledge_graph",
  ASSETS_READ: "assets_read",
  ASSETS_WRITE: "assets_write",
  MAINTENANCE: "maintenance",
  COMPLIANCE: "compliance",
  SOP_LIBRARY: "sop_library",
  USER_MANAGEMENT: "user_management",
  ROLE_MANAGEMENT: "role_management",
  SYSTEM_SETTINGS: "system_settings",
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];
