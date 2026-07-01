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
  DOCUMENTS: "documents",
  DOCUMENTS_UPLOAD: "documents_upload",
  SEARCH: "search",
  ASSETS: "assets",
  MAINTENANCE: "maintenance",
  COMPLIANCE: "compliance",
  SOP_LIBRARY: "sop_library",
  COPILOT: "copilot",
  KNOWLEDGE_GRAPH: "knowledge_graph",
  AI_AGENTS: "ai_agents",
  SETTINGS: "settings",
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];
