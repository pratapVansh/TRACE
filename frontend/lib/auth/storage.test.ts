import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Tokens must never be persisted anywhere JavaScript can read them back.
 * Previously the access AND refresh tokens were kept in localStorage, with
 * the access token also mirrored into a readable cookie, so a single XSS
 * could steal a 7-day credential.
 */

const ACCESS_TOKEN = "header.payload.signature";
const HINT_COOKIE = "trace_authed";

function createCookieJar() {
  const jar = new Map<string, string>();
  return {
    jar,
    doc: {
      get cookie(): string {
        return [...jar.entries()].map(([k, v]) => `${k}=${v}`).join("; ");
      },
      set cookie(raw: string) {
        const [pair, ...attrs] = raw.split(";").map((s) => s.trim());
        const eq = pair.indexOf("=");
        const name = pair.slice(0, eq);
        const value = pair.slice(eq + 1);
        const maxAge = attrs.find((a) => a.toLowerCase().startsWith("max-age="));
        if (maxAge && maxAge.split("=")[1].trim() === "0") {
          jar.delete(name);
        } else {
          jar.set(name, value);
        }
      },
    },
  };
}

function createLocalStorage(seed: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(seed));
  return {
    store,
    api: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    },
  };
}

async function loadStorage(seedLocalStorage: Record<string, string> = {}) {
  const cookies = createCookieJar();
  const storage = createLocalStorage(seedLocalStorage);

  vi.stubGlobal("document", cookies.doc);
  vi.stubGlobal("localStorage", storage.api);
  vi.stubGlobal("window", {
    location: { protocol: "http:" },
    localStorage: storage.api,
  });

  vi.resetModules();
  const { authStorage } = await import("./storage");
  return { authStorage, cookies, storage };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("access token handling", () => {
  it("never writes the token to localStorage", async () => {
    const { authStorage, storage } = await loadStorage();

    authStorage.setAccessToken(ACCESS_TOKEN);

    const persisted = [...storage.store.values()].join("|");
    expect(persisted).not.toContain(ACCESS_TOKEN);
    expect([...storage.store.keys()]).not.toContain("trace_access_token");
  });

  it("never writes the token to a cookie", async () => {
    const { authStorage, cookies } = await loadStorage();

    authStorage.setAccessToken(ACCESS_TOKEN);

    expect(cookies.doc.cookie).not.toContain(ACCESS_TOKEN);
    expect(cookies.jar.get(HINT_COOKIE)).toBe("1");
  });

  it("returns the token from memory", async () => {
    const { authStorage } = await loadStorage();

    expect(authStorage.getAccessToken()).toBeNull();
    authStorage.setAccessToken(ACCESS_TOKEN);
    expect(authStorage.getAccessToken()).toBe(ACCESS_TOKEN);
  });

  it("does not survive a module reload (memory-only)", async () => {
    const first = await loadStorage();
    first.authStorage.setAccessToken(ACCESS_TOKEN);

    // Simulates a page reload: fresh module instance, same cookie jar.
    const { authStorage: reloaded } = await loadStorage();
    expect(reloaded.getAccessToken()).toBeNull();
  });
});

describe("session hint", () => {
  it("is false before sign-in", async () => {
    const { authStorage } = await loadStorage();
    expect(authStorage.hasSessionHint()).toBe(false);
  });

  it("is true after setting a token", async () => {
    const { authStorage } = await loadStorage();
    authStorage.setAccessToken(ACCESS_TOKEN);
    expect(authStorage.hasSessionHint()).toBe(true);
  });

  it("is cleared on logout", async () => {
    const { authStorage, cookies } = await loadStorage();

    authStorage.setAccessToken(ACCESS_TOKEN);
    authStorage.clearTokens();

    expect(authStorage.hasSessionHint()).toBe(false);
    expect(authStorage.getAccessToken()).toBeNull();
    expect(cookies.jar.has(HINT_COOKIE)).toBe(false);
  });
});

describe("legacy credential migration", () => {
  it("purges tokens left in localStorage by the old implementation", async () => {
    const { storage } = await loadStorage({
      trace_access_token: "old-access",
      trace_refresh_token: "old-refresh",
      trace_remember_email: "user@example.com",
    });

    expect(storage.store.has("trace_access_token")).toBe(false);
    expect(storage.store.has("trace_refresh_token")).toBe(false);
    // Non-credential preferences are preserved.
    expect(storage.store.get("trace_remember_email")).toBe("user@example.com");
  });
});

describe("remembered email", () => {
  it("round-trips and clears", async () => {
    const { authStorage } = await loadStorage();

    expect(authStorage.getRememberedEmail()).toBeNull();
    authStorage.setRememberedEmail("user@example.com");
    expect(authStorage.getRememberedEmail()).toBe("user@example.com");

    authStorage.clearRememberedEmail();
    expect(authStorage.getRememberedEmail()).toBeNull();
  });
});
