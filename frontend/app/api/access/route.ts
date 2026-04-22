import { NextRequest, NextResponse } from "next/server";

import { createAccessSession, getAccessCookieName, getAccessSessionTtlSeconds } from "@/lib/accessSession";

function redirectTarget(rawTarget: FormDataEntryValue | null): string {
  const target = typeof rawTarget === "string" && rawTarget.startsWith("/") ? rawTarget : "/";
  return target.startsWith("//") ? "/" : target;
}

function redirectResponse(target: string): NextResponse {
  return new NextResponse(null, {
    status: 303,
    headers: {
      Location: target,
    },
  });
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const accessCode = process.env.FACULTY_AI_ACCESS_CODE;
  const formData = await request.formData();
  const nextUrl = redirectTarget(formData.get("next"));

  if (!accessCode || formData.get("accessCode") !== accessCode) {
    const retryUrl = `/access?error=1&next=${encodeURIComponent(nextUrl)}`;
    return redirectResponse(retryUrl);
  }

  const response = redirectResponse(nextUrl);
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
