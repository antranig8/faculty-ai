import Link from "next/link";

import styles from "./presentation.module.css";

const pages = [
  { id: "professor", label: "Professor" },
  { id: "present", label: "Present" },
  { id: "results", label: "Results" },
] as const;

export function RehearsalNav({ current }: { current: (typeof pages)[number]["id"] }) {
  return (
    <nav className={styles.pageNav} aria-label="Rehearsal pages">
      {pages.map(({ id, label }) => (
        <Link key={id} href={`/${id}`} aria-current={id === current ? "page" : undefined}>
          {label}
        </Link>
      ))}
    </nav>
  );
}
