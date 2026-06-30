const ACCESS_TOKEN_KEY = "trace_access_token";
const REFRESH_TOKEN_KEY = "trace_refresh_token";
const REMEMBER_EMAIL_KEY = "trace_remember_email";

export const authStorage = {
  getAccessToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },

  getRefreshToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  setTokens(accessToken: string, refreshToken: string): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },

  clearTokens(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
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
