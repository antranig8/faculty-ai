import type { ReactNode } from "react";

import { requireAccess } from "@/lib/requireAccess";

export const dynamic = "force-dynamic";

export default async function ResultsLayout({ children }: { children: ReactNode }) {
  await requireAccess("/results");
  return children;
}
