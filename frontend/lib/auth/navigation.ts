import {
  BookOpen,
  Bot,
  ClipboardList,
  Cog,
  Cpu,
  LayoutDashboard,
  Network,
  ScrollText,
  Search,
  Settings,
  Shield,
  Upload,
  UserCog,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { APP_ROUTES } from "@/lib/auth/routes";
import { PERMISSIONS, type Permission } from "@/types/permissions";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  permission: Permission;
};

export type NavSection = {
  title: string;
  items: NavItem[];
};

export const NAV_SECTIONS: NavSection[] = [
  {
    title: "Operations",
    items: [
      {
        href: APP_ROUTES.dashboard,
        label: "Overview",
        icon: LayoutDashboard,
        permission: PERMISSIONS.DASHBOARD,
      },
      {
        href: APP_ROUTES.documents,
        label: "Documents",
        icon: ClipboardList,
        permission: PERMISSIONS.DOCUMENTS,
      },
      {
        href: APP_ROUTES.documentsUpload,
        label: "Upload Documents",
        icon: Upload,
        permission: PERMISSIONS.DOCUMENTS_UPLOAD,
      },
      {
        href: APP_ROUTES.search,
        label: "Search",
        icon: Search,
        permission: PERMISSIONS.SEARCH,
      },
    ],
  },
  {
    title: "Intelligence",
    items: [
      {
        href: APP_ROUTES.copilot,
        label: "Copilot",
        icon: Bot,
        permission: PERMISSIONS.COPILOT,
      },
      {
        href: APP_ROUTES.knowledgeGraph,
        label: "Knowledge Graph",
        icon: Network,
        permission: PERMISSIONS.KNOWLEDGE_GRAPH,
      },
      {
        href: APP_ROUTES.aiAgents,
        label: "AI Agents",
        icon: Cpu,
        permission: PERMISSIONS.AI_AGENTS,
      },
      {
        href: APP_ROUTES.sopLibrary,
        label: "SOP Library",
        icon: BookOpen,
        permission: PERMISSIONS.SOP_LIBRARY,
      },
    ],
  },
  {
    title: "Asset & Maintenance",
    items: [
      {
        href: APP_ROUTES.assets,
        label: "Assets",
        icon: Cog,
        permission: PERMISSIONS.ASSETS,
      },
      {
        href: APP_ROUTES.assetHierarchy,
        label: "Asset Hierarchy",
        icon: Network,
        permission: PERMISSIONS.ASSETS,
      },
      {
        href: APP_ROUTES.maintenance,
        label: "Maintenance",
        icon: ClipboardList,
        permission: PERMISSIONS.MAINTENANCE,
      },
    ],
  },
  {
    title: "Governance",
    items: [
      {
        href: APP_ROUTES.compliance,
        label: "Compliance Center",
        icon: Shield,
        permission: PERMISSIONS.COMPLIANCE,
      },
      {
        href: APP_ROUTES.auditLogs,
        label: "Audit Logs",
        icon: ScrollText,
        permission: PERMISSIONS.COMPLIANCE,
      },
    ],
  },
  {
    title: "Administration",
    items: [
      {
        href: APP_ROUTES.settingsUsers,
        label: "Users",
        icon: Users,
        permission: PERMISSIONS.SETTINGS,
      },
      {
        href: APP_ROUTES.settingsRoles,
        label: "Roles & Permissions",
        icon: UserCog,
        permission: PERMISSIONS.SETTINGS,
      },
      {
        href: APP_ROUTES.settings,
        label: "System Settings",
        icon: Settings,
        permission: PERMISSIONS.SETTINGS,
      },
    ],
  },
];

export function isNavItemActive(pathname: string, href: string): boolean {
  const normalizedPath =
    pathname.endsWith("/") && pathname.length > 1
      ? pathname.slice(0, -1)
      : pathname;

  if (href === APP_ROUTES.dashboard || href === APP_ROUTES.settings) {
    return normalizedPath === href;
  }

  return normalizedPath === href || normalizedPath.startsWith(`${href}/`);
}
