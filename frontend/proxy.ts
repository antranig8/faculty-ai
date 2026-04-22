import { NextRequest, NextResponse } from "next/server";

import { getAccessCookieName, verifyAccessSession } from "./lib/accessSession";

const ACCESS_CODE = process.env.FACULTY_AI_ACCESS_CODE;

function isPublicPath(pathname: string): boolean {
  return (
    pathname === "/access"
    || pathname === "/api/access"
    || pathname.startsWith("/_next/")
    || pathname === "/favicon.ico"
  );
}

export async function proxy(request: NextRequest): Promise<NextResponse> {
  if (!ACCESS_CODE || isPublicPath(request.nextUrl.pathname)) {
    return NextResponse.next();
  }

  const session = request.cookies.get(getAccessCookieName())?.value;
  if (await verifyAccessSession(session, ACCESS_CODE)) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/access";
  url.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
