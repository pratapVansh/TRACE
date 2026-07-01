import type {
  AdminUserApiResponse,
  AdminUserListApiResponse,
  CreateAdminUserPayload,
  ResetUserPasswordPayload,
  UpdateUserRolePayload,
  UpdateUserStatusPayload,
} from "@/types/administration";

import { apiClient } from "./client";

export async function listAdminUsers(params?: {
  skip?: number;
  limit?: number;
}): Promise<AdminUserListApiResponse> {
  const { data } = await apiClient.get<AdminUserListApiResponse>("/api/admin/users", {
    params: {
      skip: params?.skip ?? 0,
      limit: params?.limit ?? 500,
    },
  });
  return data;
}

export async function createAdminUser(
  payload: CreateAdminUserPayload,
): Promise<AdminUserApiResponse> {
  const { data } = await apiClient.post<AdminUserApiResponse>(
    "/api/admin/users",
    payload,
  );
  return data;
}

export async function updateAdminUserRole(
  userId: string,
  payload: UpdateUserRolePayload,
): Promise<AdminUserApiResponse> {
  const { data } = await apiClient.patch<AdminUserApiResponse>(
    `/api/admin/users/${userId}/role`,
    payload,
  );
  return data;
}

export async function updateAdminUserStatus(
  userId: string,
  payload: UpdateUserStatusPayload,
): Promise<AdminUserApiResponse> {
  const { data } = await apiClient.patch<AdminUserApiResponse>(
    `/api/admin/users/${userId}/status`,
    payload,
  );
  return data;
}

export async function resetAdminUserPassword(
  userId: string,
  payload: ResetUserPasswordPayload,
): Promise<AdminUserApiResponse> {
  const { data } = await apiClient.patch<AdminUserApiResponse>(
    `/api/admin/users/${userId}/password`,
    payload,
  );
  return data;
}
