import Link from "next/link";

import { ProfessorCutout } from "@/components/ProfessorCutout";
import rehearsal from "@/components/presentation.module.css";
import { requireAccess } from "@/lib/requireAccess";

import styles from "./home.module.css";

export const dynamic = "force-dynamic";

const destinations = [
  { id: "present", label: "Present", description: "Start a live rehearsal" },
  { id: "professor", label: "Professor setup", description: "Set the rubric and style" },
  { id: "results", label: "Results", description: "Review saved feedback" },
];

export default async function HomePage() {
  await requireAccess("/");

  return (
    <main className={rehearsal.cockpit}>
      <div className={rehearsal.surface}>
        <div className={`${rehearsal.cockpitNav} ${styles.wordmark}`}>
          Faculty<span className={rehearsal.brandDash}>-</span>AI
        </div>
        <div className={styles.hero}>
          <header className={styles.intro}>
            <h1>Rehearse your presentation.</h1>
            <p>Upload a PowerPoint and talk through your slides. Faculty-AI listens and asks questions aloud while you present.</p>
          </header>

          <div className={`${rehearsal.stage} ${styles.scene}`}>
            <div className={styles.portrait}>
              <ProfessorCutout />
            </div>
            <nav className={styles.destinations} aria-label="Rehearsal pages">
              {destinations.map(({ id, label, description }) => (
                <Link
                  href={`/${id}`}
                  key={id}
                  className={styles.bubble}
                  aria-labelledby={`${id}-label`}
                  aria-describedby={`${id}-description`}
                >
                  <span>
                    <strong id={`${id}-label`}>{label}</strong>
                    <small id={`${id}-description`}>{description}</small>
                  </span>
                  <span className={styles.arrow} aria-hidden="true">→</span>
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </div>
    </main>
  );
}
