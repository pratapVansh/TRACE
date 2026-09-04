"use client";

import { useCallback, useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "light" | "dark";

/**
 * The applied theme lives in the DOM — the inline script in the root layout
 * sets the `dark` class before first paint. Reading it through
 * `useSyncExternalStore` keeps React in step with that external source without
 * a setState-in-effect round trip, and gives SSR a stable snapshot.
 */
function subscribe(onChange: () => void): () => void {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => observer.disconnect();
}

function getSnapshot(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/** The server always renders the dark default declared on <html>. */
function getServerSnapshot(): Theme {
  return "dark";
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const toggle = useCallback(() => {
    const next: Theme = getSnapshot() === "dark" ? "light" : "dark";
    document.documentElement.classList.toggle("dark", next === "dark");
    document.documentElement.style.colorScheme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      // Private mode or blocked storage: the toggle still works for this page.
    }
  }, []);

  const label = `Switch to ${theme === "dark" ? "light" : "dark"} theme`;

  return (
    <button
      type="button"
      onClick={toggle}
      className="inline-flex size-7 items-center justify-center rounded border border-border bg-[var(--surface-secondary)] text-muted-foreground transition-industrial hover:border-[var(--accent-steel)]/40 hover:text-foreground"
      aria-label={label}
      title={label}
    >
      {theme === "light" ? (
        <Sun className="size-3.5" strokeWidth={1.75} />
      ) : (
        <Moon className="size-3.5" strokeWidth={1.75} />
      )}
    </button>
  );
}
