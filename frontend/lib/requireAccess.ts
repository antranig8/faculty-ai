import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getAccessCookieName, verifyAccessSession } from "./accessSession";

export async function requireAccess(nextPath: string): Promise<void> {
  const accessCode = process.env.FACULTY_AI_ACCESS_CODE;
  if (!accessCode) {
    return;
  }

  const cookieStore = await cookies();
  const session = cookieStore.get(getAccessCookieName())?.value;
  if (await verifyAccessSession(session, accessCode)) {
    return;
  }

  redirect(`/access?next=${encodeURIComponent(nextPath)}`);
}
