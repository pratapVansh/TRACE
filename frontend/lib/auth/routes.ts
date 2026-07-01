import { PERMISSIONS, type Permission } from "@/types/permissions";

export const AUTH_ROUTES = {
  login: "/login",
  register: "/register",
  dashboard: "/dashboard",
  accessDenied: "/access-denied",
} as const;

export const APP_ROUTES = {
  dashboard: "/dashboard",
  documents: "/documents",
  documentsUpload: "/documents/upload",
  search: "/search",
  assets: "/assets",
  assetHierarchy: "/assets/hierarchy",
  maintenance: "/maintenance",
  compliance: "/compliance",
  auditLogs: "/audit-logs",
  sopLibrary: "/sop-library",
  copilot: "/copilot",
  knowledgeGraph: "/knowledge-graph",
  aiAgents: "/ai-agents",
  settings: "/settings",
  settingsUsers: "/settings/users",
  settingsRoles: "/settings/roles",
  accessDenied: "/access-denied",
} as const;

export const PUBLIC_AUTH_PATHS = [AUTH_ROUTES.login, AUTH_ROUTES.register] as const;

export const ROUTE_PERMISSIONS: Record<string, Permission> = {
  [APP_ROUTES.dashboard]: PERMISSIONS.DASHBOARD,
  [APP_ROUTES.documents]: PERMISSIONS.DOCUMENTS,
  [APP_ROUTES.documentsUpload]: PERMISSIONS.DOCUMENTS_UPLOAD,
  [APP_ROUTES.search]: PERMISSIONS.SEARCH,
  [APP_ROUTES.assets]: PERMISSIONS.ASSETS,
  [APP_ROUTES.assetHierarchy]: PERMISSIONS.ASSETS,
  [APP_ROUTES.maintenance]: PERMISSIONS.MAINTENANCE,
  [APP_ROUTES.compliance]: PERMISSIONS.COMPLIANCE,
  [APP_ROUTES.auditLogs]: PERMISSIONS.COMPLIANCE,
  [APP_ROUTES.sopLibrary]: PERMISSIONS.SOP_LIBRARY,
  [APP_ROUTES.copilot]: PERMISSIONS.COPILOT,
  [APP_ROUTES.knowledgeGraph]: PERMISSIONS.KNOWLEDGE_GRAPH,
  [APP_ROUTES.aiAgents]: PERMISSIONS.AI_AGENTS,
  [APP_ROUTES.settings]: PERMISSIONS.SETTINGS,
  [APP_ROUTES.settingsUsers]: PERMISSIONS.SETTINGS,
  [APP_ROUTES.settingsRoles]: PERMISSIONS.SETTINGS,
};

export function getPermissionForRoute(pathname: string): Permission | null {
  const normalizedPath =
    pathname.endsWith("/") && pathname.length > 1
      ? pathname.slice(0, -1)
      : pathname;

  if (ROUTE_PERMISSIONS[normalizedPath]) {
    return ROUTE_PERMISSIONS[normalizedPath];
  }

  const matchedRoute = Object.keys(ROUTE_PERMISSIONS)
    .sort((a, b) => b.length - a.length)
    .find((route) => normalizedPath.startsWith(`${route}/`));

  return matchedRoute ? ROUTE_PERMISSIONS[matchedRoute] : null;
}
