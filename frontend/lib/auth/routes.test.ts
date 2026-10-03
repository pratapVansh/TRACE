import { describe, expect, it } from "vitest";

import { APP_ROUTES, AUTH_ROUTES, PUBLIC_AUTH_PATHS, ROUTE_PERMISSIONS } from "./routes";
import { PERMISSIONS } from "@/types/permissions";

describe("private access routes", () => {
  it("exposes login as the only public authentication page", () => {
    expect(AUTH_ROUTES).not.toHaveProperty("register");
    expect(PUBLIC_AUTH_PATHS).toEqual(["/login"]);
  });

  it("preserves permission-gated access to core features", () => {
    expect(ROUTE_PERMISSIONS[APP_ROUTES.documents]).toBe(PERMISSIONS.DOCUMENTS_READ);
    expect(ROUTE_PERMISSIONS[APP_ROUTES.search]).toBe(PERMISSIONS.SEARCH);
    expect(ROUTE_PERMISSIONS[APP_ROUTES.copilot]).toBe(PERMISSIONS.COPILOT);
    expect(ROUTE_PERMISSIONS[APP_ROUTES.settingsUsers]).toBe(
      PERMISSIONS.USER_MANAGEMENT,
    );
  });
});
