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

export interface ActivityItem {
  id: string;
  action: string;
  subject: string;
  actor: string;
  timestamp: string;
  type: "document" | "maintenance" | "compliance" | "search" | "system";
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
  recentActivity: ActivityItem[];
  quickActions: QuickAction[];
  notifications: DashboardNotification[];
}
