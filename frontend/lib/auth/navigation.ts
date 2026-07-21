import {
  Bot,
  Cog,
  LayoutDashboard,
  Network,
  FileText,
  Search,
  Settings,
  ShieldCheck,
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
    title: "Home",
    items: [
      {
        href: APP_ROUTES.dashboard,
        label: "Dashboard",
        icon: LayoutDashboard,
        permission: PERMISSIONS.DASHBOARD,
      },
    ],
  },
  {
    title: "Knowledge",
    items: [
      {
        href: APP_ROUTES.documents,
        label: "Documents",
        icon: FileText,
        permission: PERMISSIONS.DOCUMENTS_READ,
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
    title: "AI",
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
        icon: Cog,
        permission: PERMISSIONS.AI_AGENTS,
      },
    ],
  },
  {
    title: "Operations",
    items: [
      {
        href: APP_ROUTES.assets,
        label: "Assets",
        icon: Cog,
        permission: PERMISSIONS.ASSETS_READ,
      },
      {
        href: APP_ROUTES.maintenance,
        label: "Maintenance",
        icon: Cog,
        permission: PERMISSIONS.MAINTENANCE,
      },
      {
        href: APP_ROUTES.compliance,
        label: "Compliance",
        icon: ShieldCheck,
        permission: PERMISSIONS.COMPLIANCE,
      },
    ],
  },
  {
    title: "Administration",
    items: [
      {
        href: APP_ROUTES.settings,
        label: "Settings",
        icon: Settings,
        permission: PERMISSIONS.SYSTEM_SETTINGS,
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
