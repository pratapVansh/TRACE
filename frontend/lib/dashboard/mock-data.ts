import {
  Bot,
  ClipboardList,
  FileText,
  HeartPulse,
  Search,
  Upload,
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
      id: "qa-4",
      label: "Ask Copilot",
      description: "Natural language queries",
      href: APP_ROUTES.copilot,
      icon: Bot,
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
