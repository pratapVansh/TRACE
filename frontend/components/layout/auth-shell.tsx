"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { AuthBrandPanel } from "@/components/auth/auth-brand-panel";
import { TraceLogo } from "@/components/common/trace-logo";

interface AuthShellProps {
  title: string;
  subtitle: string;
  footer: ReactNode;
  children: ReactNode;
}

export function AuthShell({
  title,
  subtitle,
  footer,
  children,
}: AuthShellProps) {
  return (
    <div className="min-h-screen bg-background lg:grid lg:grid-cols-[1.1fr_0.9fr]">
      <div className="hidden lg:block">
        <AuthBrandPanel />
      </div>

      <div className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-8 lg:px-10 xl:px-14">
        <div className="w-full max-w-[440px] animate-in fade-in slide-in-from-bottom-1 duration-200">
          <div className="mb-8 lg:hidden">
            <TraceLogo size="md" />
          </div>

          <div className="industrial-card p-7 sm:p-9">
            <div className="mb-8 space-y-3">
              <p className="section-label">Secure access</p>
              <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-[1.75rem]">
                {title}
              </h2>
              <p className="page-subtitle text-sm">{subtitle}</p>
            </div>

            {children}
          </div>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            {footer}
          </div>
        </div>
      </div>
    </div>
  );
}

export function AuthLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className="font-medium text-[var(--accent-steel-muted)] transition-industrial hover:text-white"
    >
      {children}
    </Link>
  );
}
