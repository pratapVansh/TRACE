"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { useAuth } from "@/hooks/use-auth";
import { AUTH_ROUTES } from "@/lib/auth/routes";

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    router.replace(
      isAuthenticated ? AUTH_ROUTES.dashboard : AUTH_ROUTES.login,
    );
  }, [isAuthenticated, isLoading, router]);

  return <AuthLoadingScreen label="Loading TRACE workspace…" />;
}
