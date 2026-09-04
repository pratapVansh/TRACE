import {
  BookOpen,
  Bot,
  ClipboardList,
  Cog,
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
        permission: PERMISSIONS.DOCUMENTS_READ,
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
    ],
  },
  {
    title: "Governance",
    items: [
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
        permission: PERMISSIONS.USER_MANAGEMENT,
      },
    ],
  },
];

export function isNavItemActive(pathname: string, href: string): boolean {
  const normalizedPath =
    pathname.endsWith("/") && pathname.length > 1
      ? pathname.slice(0, -1)
      : pathname;

  if (href === APP_ROUTES.dashboard) {
    return normalizedPath === href;
  }

  return normalizedPath === href || normalizedPath.startsWith(`${href}/`);
}
