/**
 * Auth token storage.
 *
 * Tokens are deliberately NOT persisted to localStorage. Previously both
 * the access and refresh token were kept there (plus the access token
 * mirrored into a readable cookie), so any XSS could exfiltrate a 7-day
 * credential.
 *
 * Now:
 *  - refresh token — httpOnly cookie set by the backend, unreachable from JS
 *  - access token  — in memory only, lost on reload and silently restored
 *                    via POST /api/auth/refresh
 *  - session hint  — a valueless cookie so `proxy.ts` can gate routes
 *                    without a credential ever being readable
 */

const REMEMBER_EMAIL_KEY = "trace_remember_email";

/** Non-sensitive marker read by proxy.ts. Contains no credential. */
const SESSION_HINT_COOKIE = "trace_authed";

/** Keys written by the pre-cookie implementation; purged on load. */
const LEGACY_TOKEN_KEYS = ["trace_access_token", "trace_refresh_token"];
const LEGACY_TOKEN_COOKIE = "access_token";

let accessTokenInMemory: string | null = null;

function isSecureContext(): boolean {
  return typeof window !== "undefined" && window.location.protocol === "https:";
}

function writeCookie(name: string, value: string, maxAgeSeconds: number): void {
  if (typeof document === "undefined") return;
  const secure = isSecureContext() ? "; Secure" : "";
  document.cookie = `${name}=${value}; path=/; max-age=${maxAgeSeconds}; SameSite=Lax${secure}`;
}

function deleteCookie(name: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`;
}

function hasCookie(name: string): boolean {
  if (typeof document === "undefined") return false;
  return document.cookie
    .split(";")
    .some((entry) => entry.trim().startsWith(`${name}=`));
}

/**
 * Remove credentials written by the previous localStorage implementation so
 * upgrading users are not left with a stale token sitting in storage.
 */
function purgeLegacyCredentials(): void {
  if (typeof window === "undefined") return;
  LEGACY_TOKEN_KEYS.forEach((key) => localStorage.removeItem(key));
  deleteCookie(LEGACY_TOKEN_COOKIE);
}

purgeLegacyCredentials();

export const authStorage = {
  getAccessToken(): string | null {
    return accessTokenInMemory;
  },

  setAccessToken(accessToken: string): void {
    accessTokenInMemory = accessToken;
    // Mirror only the *fact* of a session, never the token itself.
    // 7 days, matching the refresh cookie's lifetime.
    writeCookie(SESSION_HINT_COOKIE, "1", 60 * 60 * 24 * 7);
  },

  /** True when a session probably exists and a silent refresh is worth trying. */
  hasSessionHint(): boolean {
    return hasCookie(SESSION_HINT_COOKIE);
  },

  clearTokens(): void {
    accessTokenInMemory = null;
    deleteCookie(SESSION_HINT_COOKIE);
    purgeLegacyCredentials();
  },

  getRememberedEmail(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(REMEMBER_EMAIL_KEY);
  },

  setRememberedEmail(email: string): void {
    localStorage.setItem(REMEMBER_EMAIL_KEY, email);
  },

  clearRememberedEmail(): void {
    localStorage.removeItem(REMEMBER_EMAIL_KEY);
  },
};
