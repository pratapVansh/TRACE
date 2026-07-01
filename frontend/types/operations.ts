export type HealthStatus = "healthy" | "degraded" | "critical" | "offline";

export type EquipmentType =
  | "Centrifugal Pump"
  | "Heat Exchanger"
  | "Pressure Vessel"
  | "Compressor"
  | "Control Valve"
  | "Furnace"
  | "Storage Tank"
  | "Flare Stack";

export interface IndustrialAsset {
  id: string;
  tag: string;
  name: string;
  equipmentType: EquipmentType;
  location: string;
  unit: string;
  healthStatus: HealthStatus;
  maintenanceDue: string;
  maintenanceDueDate: string;
  criticality: "high" | "medium" | "low";
}

export interface AssetHierarchyNode {
  id: string;
  name: string;
  type: "site" | "unit" | "system" | "equipment";
  tag?: string;
  assetCount?: number;
  healthStatus?: HealthStatus;
  children?: AssetHierarchyNode[];
}

export type WorkOrderPriority = "critical" | "high" | "medium" | "low";
export type WorkOrderStatus = "open" | "in_progress" | "scheduled" | "completed" | "overdue";

export interface UpcomingMaintenance {
  id: string;
  assetTag: string;
  assetName: string;
  task: string;
  scheduledDate: string;
  type: "preventive" | "predictive" | "corrective";
  assignedTo: string;
}

export interface WorkOrder {
  id: string;
  woNumber: string;
  title: string;
  assetTag: string;
  priority: WorkOrderPriority;
  status: WorkOrderStatus;
  assignedTo: string;
  dueDate: string;
  department: string;
}

export type ComplianceStandardStatus = "compliant" | "review" | "at_risk" | "non_compliant";

export interface ComplianceStandard {
  id: string;
  name: string;
  shortName: string;
  score: number;
  status: ComplianceStandardStatus;
  lastAudit: string;
  nextAudit: string;
  openFindings: number;
}

export interface AuditSummaryItem {
  id: string;
  auditName: string;
  standard: string;
  auditor: string;
  completedAt: string;
  score: number;
  findings: number;
  status: "passed" | "conditional" | "failed";
}

export interface SopDocument {
  id: string;
  code: string;
  title: string;
  category: string;
  version: string;
  department: string;
  approvedBy: string;
  lastReviewed: string;
  status: "active" | "draft" | "archived" | "review";
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  user: string;
  role: string;
  action: string;
  resource: string;
  outcome: "success" | "denied" | "warning";
  ipAddress: string;
}
