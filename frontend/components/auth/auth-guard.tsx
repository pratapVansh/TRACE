"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { useAuth } from "@/hooks/use-auth";
import { AUTH_ROUTES } from "@/lib/auth/routes";

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(AUTH_ROUTES.login);
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return <AuthLoadingScreen />;
  }

  if (!isAuthenticated) {
    return <AuthLoadingScreen label="Redirecting to sign in…" />;
  }

  return <>{children}</>;
}

export function GuestGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(AUTH_ROUTES.dashboard);
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return <AuthLoadingScreen />;
  }

  if (isAuthenticated) {
    return <AuthLoadingScreen label="Redirecting to dashboard…" />;
  }

  return <>{children}</>;
}
