"use client";

import { useEffect, useState } from "react";

import { FeedbackPanel } from "@/components/FeedbackPanel";
import { RehearsalNav } from "@/components/RehearsalNav";
import styles from "@/components/presentation.module.css";
import { getFeedback } from "@/lib/api";
import { latestRehearsal, waitForRehearsalUpdates } from "@/lib/rehearsalSession";
import type { FeedbackItem } from "@/lib/types";

type Results =
  | { status: "loading" | "none" | "missing" | "error" }
  | { status: "ready"; feedback: FeedbackItem[] };

export default function ResultsPage() {
  const [results, setResults] = useState<Results>({ status: "loading" });

  useEffect(() => {
    const sessionId = latestRehearsal();
    if (!sessionId) {
      setResults({ status: "none" });
      return;
    }

    let cancelled = false;
    async function loadResults(id: string) {
      try {
        await waitForRehearsalUpdates(id);
        if (cancelled) {
          return;
        }
        const feedback = await getFeedback(id);
        if (!cancelled) {
          setResults(feedback ? { status: "ready", feedback } : { status: "missing" });
        }
      } catch {
        if (!cancelled) {
          setResults({ status: "error" });
        }
      }
    }
    void loadResults(sessionId);
    return () => { cancelled = true; };
  }, []);

  const feedback = results.status === "ready" ? results.feedback : undefined;
  const addressed = feedback?.filter((item) => item.resolved).length ?? 0;

  return (
    <main className={styles.cockpit}>
      <div className={styles.surface}>
        <RehearsalNav current="results" />
        <header className={styles.pageHeader}>
          <h1>Rehearsal results</h1>
          <p className={styles.secondary}>Faculty feedback from your latest rehearsal.</p>
        </header>
        <section className={styles.details} aria-label="Saved faculty feedback">
          {results.status === "loading" ? <p role="status">Loading results…</p> : null}
          {results.status === "none" ? <p>Start a live rehearsal from Present to see your results here.</p> : null}
          {results.status === "missing" ? <p>This rehearsal is no longer saved. Start a new one from Present.</p> : null}
          {results.status === "error" ? <p className={styles.error} role="alert">Unable to load results. Check that the local backend is running and reload this page.</p> : null}
          {feedback ? (
            <>
              <p className={styles.resultCounts}>
                <span><strong>{feedback.length}</strong> {feedback.length === 1 ? "question" : "questions"}</span>
                <span><strong>{addressed}</strong> addressed</span>
                <span><strong>{feedback.length - addressed}</strong> open</span>
              </p>
              {feedback.length > 0 ? <FeedbackPanel feedback={feedback} /> : <p className={styles.secondary}>No faculty questions were asked in this rehearsal.</p>}
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
