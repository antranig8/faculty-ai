"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getResults } from "@/lib/api";
import type { FinalEvaluation } from "@/lib/types";

export default function ResultsPage() {
  const [results, setResults] = useState<FinalEvaluation[]>([]);
  const [status, setStatus] = useState("Loading presentation results.");

  useEffect(() => {
    getResults()
      .then((loaded) => {
        setResults(loaded);
        setStatus(loaded.length ? "Presentation results loaded." : "No presentation results saved yet.");
      })
      .catch((error) => setStatus(error instanceof Error ? error.message : "Unable to load results."));
  }, []);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Faculty AI</p>
          <h1>Presentation Results</h1>
        </div>
        <Link href="/present">Back to presentation mode</Link>
      </header>

      <section className="professor-page">
        <p className="muted">{status}</p>
        {results.map((result) => (
          <article className="setup-panel" key={result.sessionId}>
            <div className="panel-header">
              <div>
                <p className="eyebrow">{result.courseName}</p>
                <h2>
                  {result.projectTitle}: {result.overallGrade} ({result.numericScore})
                </h2>
              </div>
              <span>{new Date(result.createdAt).toLocaleString()}</span>
            </div>
            <p>{result.summary}</p>
            <div className="feedback-list">
              {result.biggestQuestions.map((question) => (
                <article className="feedback-card question" key={question}>
                  <p>{question}</p>
                </article>
              ))}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
