"use client";

import { AuthProvider } from "@/contexts/auth-context";
import { DocumentsProvider } from "@/contexts/documents-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <DocumentsProvider>{children}</DocumentsProvider>
    </AuthProvider>
  );
}
