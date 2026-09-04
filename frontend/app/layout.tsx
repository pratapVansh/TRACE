import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Providers } from "./providers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TRACE — Industrial Knowledge Intelligence Platform",
  description:
    "Technical Records & Asset Compliance Engine — industrial knowledge intelligence for enterprise operations.",
};

/**
 * Applies the saved theme before first paint.
 *
 * Runs synchronously while the browser parses <head>, so the correct palette
 * is in place before anything is painted — a `useEffect` would repaint and
 * flash. Toggling the `dark` class (rather than a data attribute) keeps
 * Tailwind's existing `@custom-variant dark (&:is(.dark *))` working.
 */
const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("theme");if(!t){t=window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}document.documentElement.classList.toggle("dark",t!=="light");document.documentElement.style.colorScheme=t==="light"?"light":"dark"}catch(e){}})()`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      // Server renders the dark default; the script below may switch it to
      // light before hydration, which React must not treat as a mismatch.
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} dark h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-full bg-background text-foreground">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
