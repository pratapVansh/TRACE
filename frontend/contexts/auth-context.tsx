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
  refreshToken: string | null;
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
  refreshToken: string | null;
}

async function resolveInitialAuthState(): Promise<ResolvedAuthState> {
  const accessToken = authStorage.getAccessToken();
  const refreshToken = authStorage.getRefreshToken();

  if (!accessToken || !refreshToken) {
    authStorage.clearTokens();
    return { user: null, accessToken: null, refreshToken: null };
  }

  try {
    const user = await getCurrentUserRequest();
    return { user, accessToken, refreshToken };
  } catch {
    try {
      const tokens = await refreshRequest(refreshToken);
      authStorage.setTokens(tokens.access_token, tokens.refresh_token);
      const user = await getCurrentUserRequest();
      return {
        user,
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      };
    } catch {
      authStorage.clearTokens();
      return { user: null, accessToken: null, refreshToken: null };
    }
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const applyTokens = useCallback((nextAccessToken: string, nextRefreshToken: string) => {
    authStorage.setTokens(nextAccessToken, nextRefreshToken);
    setAccessToken(nextAccessToken);
    setRefreshToken(nextRefreshToken);
  }, []);

  const clearAuth = useCallback(() => {
    authStorage.clearTokens();
    setUser(null);
    setAccessToken(null);
    setRefreshToken(null);
  }, []);

  const refresh = useCallback(async () => {
    const storedRefreshToken = authStorage.getRefreshToken();
    if (!storedRefreshToken) {
      throw new Error("No refresh token available");
    }

    const tokens = await refreshRequest(storedRefreshToken);
    applyTokens(tokens.access_token, tokens.refresh_token);
  }, [applyTokens]);

  useEffect(() => {
    let cancelled = false;

    resolveInitialAuthState().then((state) => {
      if (cancelled) return;
      setUser(state.user);
      setAccessToken(state.accessToken);
      setRefreshToken(state.refreshToken);
      setIsLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (payload: LoginRequest) => {
      const tokens = await loginRequest(payload);
      applyTokens(tokens.access_token, tokens.refresh_token);
      const currentUser = await getCurrentUserRequest();
      setUser(currentUser);
    },
    [applyTokens],
  );

  const register = useCallback(async (payload: RegisterRequest) => {
    await registerRequest(payload);
  }, []);

  const logout = useCallback(async () => {
    const storedRefreshToken = authStorage.getRefreshToken();
    try {
      if (storedRefreshToken) {
        await logoutRequest(storedRefreshToken);
      }
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
      refreshToken,
      isLoading,
      isAuthenticated: Boolean(user && accessToken),
      login,
      register,
      logout,
      refresh,
    }),
    [
      user,
      accessToken,
      refreshToken,
      isLoading,
      login,
      register,
      logout,
      refresh,
    ],
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
