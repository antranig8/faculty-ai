import { NextRequest, NextResponse } from "next/server";

import { createAccessSession, getAccessCookieName, getAccessSessionTtlSeconds } from "@/lib/accessSession";

function redirectTarget(request: NextRequest, rawTarget: FormDataEntryValue | null): URL {
  const target = typeof rawTarget === "string" && rawTarget.startsWith("/") ? rawTarget : "/";
  return new URL(target, request.url);
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const accessCode = process.env.FACULTY_AI_ACCESS_CODE;
  const formData = await request.formData();
  const nextUrl = redirectTarget(request, formData.get("next"));

  if (!accessCode || formData.get("accessCode") !== accessCode) {
    const retryUrl = new URL("/access", request.url);
    retryUrl.searchParams.set("error", "1");
    retryUrl.searchParams.set("next", nextUrl.pathname + nextUrl.search);
    return NextResponse.redirect(retryUrl, { status: 303 });
  }

  const response = NextResponse.redirect(nextUrl, { status: 303 });
  response.cookies.set({
    name: getAccessCookieName(),
    value: await createAccessSession(accessCode),
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: getAccessSessionTtlSeconds(),
    path: "/",
  });
  return response;
}
