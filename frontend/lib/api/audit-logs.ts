import type {
  AuditLogApiResponse,
  AuditLogEntry,
  AuditLogListApiResponse,
} from "@/types/operations";

import { apiClient } from "./client";

export type AuditLogListParams = {
  skip?: number;
  limit?: number;
  user?: string;
  action?: string;
  dateFrom?: string;
  dateTo?: string;
};

export async function listAuditLogs(
  params: AuditLogListParams = {},
): Promise<AuditLogListApiResponse> {
  const { data } = await apiClient.get<AuditLogListApiResponse>("/api/audit-logs", {
    params: {
      skip: params.skip ?? 0,
      limit: params.limit ?? 50,
      user: params.user || undefined,
      action: params.action || undefined,
      date_from: params.dateFrom || undefined,
      date_to: params.dateTo || undefined,
    },
  });
  return data;
}

export function mapAuditLogFromApi(log: AuditLogApiResponse): AuditLogEntry {
  return {
    id: log.id,
    timestamp: log.timestamp,
    // A log with no username was written by a background job, not a person.
    user: log.username ?? "System",
    action: log.action,
    resource: log.entity_id
      ? `${log.entity_type} · ${log.entity_id.slice(0, 8)}`
      : log.entity_type,
    outcome: log.status === "success" ? "success" : "failure",
    ipAddress: log.ip_address,
    errorMessage: log.error_message,
  };
}
