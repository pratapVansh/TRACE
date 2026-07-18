import { apiClient } from "./client";

export interface DashboardApiResponse {
  document_count: number;
  entity_count: number | null;
  relationship_count: number | null;
  conversation_count: number;
  pending_jobs: number;
  recent_uploads: {
    id: string;
    title: string;
    filename: string;
    status: string;
    uploaded_at: string;
  }[];
  qdrant_connected: boolean;
  neo4j_connected: boolean;
  db_connected: boolean;
}

export async function fetchDashboard(): Promise<DashboardApiResponse> {
  const { data } = await apiClient.get<DashboardApiResponse>("/api/dashboard");
  return data;
}
