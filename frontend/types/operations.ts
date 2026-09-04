// The operations domain (assets, maintenance, compliance, SOPs) has no
// backend, so its pages were removed. Only the audit-log shape remains,
// backed by GET /api/audit-logs.

export interface AuditLogApiResponse {
  id: string;
  timestamp: string;
  user_id: string | null;
  username: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  ip_address: string | null;
  status: string;
  error_message: string | null;
}

export interface AuditLogListApiResponse {
  items: AuditLogApiResponse[];
  total: number;
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

// Mirrors the audit_logs table. There is no role column, so the entry
// carries the username the action was recorded against and nothing more.
export interface AuditLogEntry {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  resource: string;
  outcome: "success" | "failure";
  ipAddress: string | null;
  errorMessage: string | null;
}
