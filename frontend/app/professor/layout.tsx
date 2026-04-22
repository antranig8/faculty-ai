import type { ReactNode } from "react";

import { requireAccess } from "@/lib/requireAccess";

export const dynamic = "force-dynamic";

export default async function ProfessorLayout({ children }: { children: ReactNode }) {
  await requireAccess("/professor");
  return children;
}
