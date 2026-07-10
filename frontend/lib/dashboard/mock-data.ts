import {
  Bot,
  ClipboardList,
  Cog,
  FileText,
  HeartPulse,
  Search,
  ShieldCheck,
  Upload,
  Wrench,
} from "lucide-react";

import { APP_ROUTES } from "@/lib/auth/routes";
import type { ExecutiveDashboardData } from "@/types/dashboard";

export const EXECUTIVE_DASHBOARD_DATA: ExecutiveDashboardData = {
  facilityName: "",
  lastUpdated: "",
  kpis: [],
  recentDocuments: [],
  recentActivity: [],
  complianceMetrics: [],
  assetCategories: [],
  recentSearches: [],
  quickActions: [
    {
      id: "qa-1",
      label: "Upload Document",
      description: "Ingest new technical records",
      href: APP_ROUTES.documentsUpload,
      icon: Upload,
    },
    {
      id: "qa-2",
      label: "View Maintenance",
      description: "Review open work orders",
      href: APP_ROUTES.maintenance,
      icon: Wrench,
    },
    {
      id: "qa-3",
      label: "Compliance Check",
      description: "Run standards audit",
      href: APP_ROUTES.compliance,
      icon: ShieldCheck,
    },
    {
      id: "qa-4",
      label: "Ask Copilot",
      description: "Natural language queries",
      href: APP_ROUTES.copilot,
      icon: Bot,
    },
    {
      id: "qa-5",
      label: "Asset Registry",
      description: "Browse equipment tags",
      href: APP_ROUTES.assets,
      icon: Cog,
    },
    {
      id: "qa-6",
      label: "Semantic Search",
      description: "Search knowledge base",
      href: APP_ROUTES.search,
      icon: Search,
    },
  ],
  notifications: [],
};
