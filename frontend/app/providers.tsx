"use client";

import { AuthProvider } from "@/contexts/auth-context";
import { DocumentsProvider } from "@/contexts/documents-context";
import { ThemeProvider } from "@/contexts/theme-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <DocumentsProvider>{children}</DocumentsProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
