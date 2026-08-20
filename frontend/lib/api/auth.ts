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

/**
 * Rotate the session. The refresh token is sent automatically as an
 * httpOnly cookie, so no argument (and no request body) is needed.
 */
export async function refreshRequest(): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/api/auth/refresh", {});
  return data;
}

/** Revokes the refresh token server-side and expires the cookie. */
export async function logoutRequest(): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>("/api/auth/logout", {});
  return data;
}

export async function getCurrentUserRequest(): Promise<User> {
  const { data } = await apiClient.get<User>("/api/auth/me");
  return data;
}
