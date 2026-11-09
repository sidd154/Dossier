import { NextResponse, type NextRequest } from "next/server";

// UX-only gate. Every authorisation decision is enforced by the API.
const PUBLIC_PATHS = ["/login", "/403"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has("access_token");
  const isPublic = PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  );

  if (!hasSession && !isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  // Deliberately no "/login -> /admin" redirect here. A stale access cookie with a
  // revoked refresh token would otherwise loop between the two pages. The login page
  // itself checks for a live session and forwards authenticated users.
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|demo-api|_next/static|_next/image|favicon.ico).*)"],
};
