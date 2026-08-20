import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const publicRoutes = new Set(["/login", "/register", "/maintenance"]);

/**
 * Route gating.
 *
 * This checks a valueless `trace_authed` marker, not a token. It previously
 * read an `access_token` cookie, which required mirroring a real JWT into a
 * JS-readable cookie purely so this file could see it.
 *
 * This is a UX redirect only — it never validated the token's signature or
 * expiry even before. Real authorization is enforced by the backend on every
 * request; treat this as a convenience, not a security boundary.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get("trace_authed")?.value);

  if (publicRoutes.has(pathname) || pathname === "/") {
    if (hasSession && pathname !== "/") {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return NextResponse.next();
  }

  if (!hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/health).*)"],
};
