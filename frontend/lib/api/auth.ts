import type {
  LoginRequest,
  MessageResponse,
  RegisterRequest,
  TokenResponse,
  User,
} from "@/types/auth";

import { apiClient } from "./client";

export async function loginRequest(payload: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/api/auth/login", payload);
  return data;
}

export async function registerRequest(
  payload: RegisterRequest,
): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>(
    "/api/auth/register",
    payload,
  );
  return data;
}

export async function refreshRequest(refreshToken: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/api/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}

export async function logoutRequest(refreshToken: string): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>("/api/auth/logout", {
    refresh_token: refreshToken,
  });
  return data;
}

export async function getCurrentUserRequest(): Promise<User> {
  const { data } = await apiClient.get<User>("/api/auth/me");
  return data;
}
