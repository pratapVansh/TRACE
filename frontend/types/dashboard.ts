import type { LucideIcon } from "lucide-react";

export type ChangeType = "neutral" | "positive" | "warning" | "negative";

export interface DashboardKpi {
  id: string;
  title: string;
  value: string;
  change: string;
  changeType: ChangeType;
  icon: LucideIcon;
}

export interface RecentDocument {
  id: string;
  title: string;
  type: string;
  unit: string;
  updatedAt: string;
  status: "indexed" | "processing" | "review";
}

export interface ActivityItem {
  id: string;
  action: string;
  subject: string;
  actor: string;
  timestamp: string;
  type: "document" | "maintenance" | "compliance" | "search" | "system";
}

export interface ComplianceMetric {
  id: string;
  standard: string;
  score: number;
  status: "compliant" | "review" | "at-risk";
  dueDate?: string;
}

export interface AssetCategory {
  id: string;
  label: string;
  count: number;
  percentage: number;
  color: string;
}

export interface RecentSearch {
  id: string;
  query: string;
  results: number;
  timestamp: string;
  user: string;
}

export interface QuickAction {
  id: string;
  label: string;
  description: string;
  href: string;
  icon: LucideIcon;
}

export interface DashboardNotification {
  id: string;
  title: string;
  message: string;
  timestamp: string;
  priority: "low" | "medium" | "high";
  read: boolean;
}

export interface ExecutiveDashboardData {
  facilityName: string;
  lastUpdated: string;
  kpis: DashboardKpi[];
  recentDocuments: RecentDocument[];
  recentActivity: ActivityItem[];
  complianceMetrics: ComplianceMetric[];
  assetCategories: AssetCategory[];
  recentSearches: RecentSearch[];
  quickActions: QuickAction[];
  notifications: DashboardNotification[];
}
