import Link from "next/link";

export default function HomePage() {
  return (
    <main className="home-screen">
      <section>
        <p className="eyebrow">Faculty AI</p>
        <h1>Practice the questions before they are asked.</h1>
        <p>
          Professors configure the rubric. Students upload a deck and rehearse against faculty-style questions.
        </p>
        <div className="home-actions">
          <Link href="/professor">Professor setup</Link>
          <Link href="/present">Student presentation mode</Link>
          <Link href="/results">Results</Link>
        </div>
      </section>
    </main>
  );
}
