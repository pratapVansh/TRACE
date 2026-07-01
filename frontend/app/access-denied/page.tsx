"use client";

import { ShieldX } from "lucide-react";
import Link from "next/link";

import { AuthGuard } from "@/components/auth/auth-guard";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { useAuth } from "@/hooks/use-auth";
import { AUTH_ROUTES } from "@/lib/auth/routes";

function AccessDeniedContent() {
  const { user } = useAuth();

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 lg:gap-10">
      <section className="industrial-card p-8 sm:p-10">
        <div className="flex flex-col items-start gap-6 sm:flex-row sm:items-center">
          <div className="flex size-14 shrink-0 items-center justify-center rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 text-[var(--danger)]">
            <ShieldX className="size-7" strokeWidth={1.75} />
          </div>
          <div className="space-y-3">
            <p className="section-label">Access control</p>
            <h2 className="page-title">Access denied</h2>
            <p className="page-subtitle max-w-xl">
              Your current role does not include permission to view this page.
              Contact an administrator if you believe you need additional access.
            </p>
            {user?.role ? (
              <p className="text-sm text-muted-foreground">
                Signed in as <span className="text-white">{user.full_name}</span>{" "}
                with role <span className="text-white">{user.role}</span>.
              </p>
            ) : null}
          </div>
        </div>

        <div className="mt-8">
          <Link
            href={AUTH_ROUTES.dashboard}
            className="inline-flex h-11 items-center rounded-xl bg-[var(--accent-steel)] px-5 text-sm font-medium text-white transition-industrial hover:bg-[#6a8eb5]"
          >
            Return to dashboard
          </Link>
        </div>
      </section>
    </div>
  );
}

export default function AccessDeniedPage() {
  return (
    <AuthGuard>
      <DashboardLayout>
        <AccessDeniedContent />
      </DashboardLayout>
    </AuthGuard>
  );
}
