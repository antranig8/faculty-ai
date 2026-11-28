import { NextRequest, NextResponse } from "next/server";

import { createAccessSession, getAccessCookieName, getAccessRedirectTarget, getAccessSessionTtlSeconds } from "@/lib/accessSession";

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
  const nextUrl = getAccessRedirectTarget(formData.get("next"));

  if (!accessCode) {
    return redirectResponse(nextUrl);
  }
  if (formData.get("accessCode") !== accessCode) {
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
