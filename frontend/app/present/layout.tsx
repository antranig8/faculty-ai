import type { ReactNode } from "react";

import { requireAccess } from "@/lib/requireAccess";

export const dynamic = "force-dynamic";

export default async function PresentLayout({ children }: { children: ReactNode }) {
  await requireAccess("/present");
  return children;
}
