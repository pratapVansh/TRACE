"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  getCurrentUserRequest,
  loginRequest,
  logoutRequest,
  refreshRequest,
  registerRequest,
} from "@/lib/api/auth";
import { authStorage } from "@/lib/auth/storage";
import type { LoginRequest, RegisterRequest, User } from "@/types/auth";

interface AuthContextValue {
  user: User | null;
  accessToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginRequest) => Promise<void>;
  register: (payload: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface ResolvedAuthState {
  user: User | null;
  accessToken: string | null;
}

const SIGNED_OUT: ResolvedAuthState = { user: null, accessToken: null };

/**
 * Restore the session on page load.
 *
 * The access token lives in memory, so it is always gone after a reload.
 * The httpOnly refresh cookie is the only surviving credential — exchange
 * it for a fresh access token. The session hint avoids firing a guaranteed
 * 401 for visitors who were never signed in.
 */
async function resolveInitialAuthState(): Promise<ResolvedAuthState> {
  if (!authStorage.hasSessionHint()) {
    authStorage.clearTokens();
    return SIGNED_OUT;
  }

  try {
    const tokens = await refreshRequest();
    authStorage.setAccessToken(tokens.access_token);
    const user = await getCurrentUserRequest();
    return { user, accessToken: tokens.access_token };
  } catch {
    // Cookie missing, expired, or already revoked.
    authStorage.clearTokens();
    return SIGNED_OUT;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const applyAccessToken = useCallback((nextAccessToken: string) => {
    authStorage.setAccessToken(nextAccessToken);
    setAccessToken(nextAccessToken);
  }, []);

  const clearAuth = useCallback(() => {
    authStorage.clearTokens();
    setUser(null);
    setAccessToken(null);
  }, []);

  const refresh = useCallback(async () => {
    const tokens = await refreshRequest();
    applyAccessToken(tokens.access_token);
  }, [applyAccessToken]);

  useEffect(() => {
    let cancelled = false;

    resolveInitialAuthState().then((state) => {
      if (cancelled) return;
      setUser(state.user);
      setAccessToken(state.accessToken);
      setIsLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (payload: LoginRequest) => {
      const tokens = await loginRequest(payload);
      applyAccessToken(tokens.access_token);
      const currentUser = await getCurrentUserRequest();
      setUser(currentUser);
    },
    [applyAccessToken],
  );

  const register = useCallback(async (payload: RegisterRequest) => {
    await registerRequest(payload);
  }, []);

  const logout = useCallback(async () => {
    try {
      // The httpOnly cookie identifies the session; the server revokes it
      // and expires the cookie.
      await logoutRequest();
    } catch {
      // Session may already be invalid — still clear local state.
    } finally {
      clearAuth();
    }
  }, [clearAuth]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      accessToken,
      isLoading,
      isAuthenticated: Boolean(user && accessToken),
      login,
      register,
      logout,
      refresh,
    }),
    [user, accessToken, isLoading, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
