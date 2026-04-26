import Link from "next/link";

import { requireAccess } from "@/lib/requireAccess";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  await requireAccess("/");

  return (
    <main className="home-screen">
      <section className="hero-shell">
        <header className="hero-nav">
          <div>
            <p className="eyebrow">Faculty AI</p>
            <p className="hero-brand-note">AI rehearsal for academic presentations</p>
          </div>
          <nav className="hero-nav-links" aria-label="Primary">
            <Link href="/professor">Professor</Link>
            <Link href="/present">Present</Link>
            <Link href="/results">Results</Link>
          </nav>
        </header>

        <div className="hero-grid">
          <div className="hero-copy">
            <p className="hero-kicker">Live faculty simulation</p>
            <h1>Practice the defense before the room asks the question.</h1>
            <p className="hero-summary">
              Configure faculty expectations, upload a deck, and rehearse with disciplined follow-up questions in one
              black-and-white workspace.
            </p>
            <div className="home-actions">
              <Link className="hero-primary-link" href="/present">
                Start rehearsal
              </Link>
              <Link className="hero-secondary-link" href="/professor">
                Configure rubric
              </Link>
            </div>
            <div className="hero-meta">
              <div>
                <span>Mode</span>
                <strong>Professor-defined questioning</strong>
              </div>
              <div>
                <span>Use case</span>
                <strong>Deck practice before grading</strong>
              </div>
              <div>
                <span>Output</span>
                <strong>Live critique and final results</strong>
              </div>
            </div>
          </div>

          <aside className="hero-panel" aria-label="Platform preview">
            <div className="hero-panel-header">
              <p className="hero-panel-kicker">Session flow</p>
            </div>
            <div className="hero-panel-stack">
              <article>
                <span>01</span>
                <strong>Professor setup</strong>
                <p>Define rubric, expectations, and likely lines of questioning.</p>
              </article>
              <article>
                <span>02</span>
                <strong>Presentation mode</strong>
                <p>Advance through slides while the system listens for weak reasoning and unclear claims.</p>
              </article>
              <article>
                <span>03</span>
                <strong>Results</strong>
                <p>Review critique, concerns, and prepared follow-ups after the session closes.</p>
              </article>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
