"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ProfessorConfigForm } from "@/components/ProfessorConfigForm";
import { getProfessorConfig, saveProfessorConfig } from "@/lib/api";
import type { ProfessorConfig } from "@/lib/types";

const fallbackConfig: ProfessorConfig = {
  courseName: "ENES 104",
  assignmentName: "Project Presentation",
  rubric: ["clarity", "technical justification", "evidence", "evaluation", "feasibility"],
  questionStyle: "skeptical but fair faculty examiner",
  assignmentContext: "",
};

export default function ProfessorPage() {
  const [config, setConfig] = useState<ProfessorConfig>(fallbackConfig);
  const [status, setStatus] = useState("Loading professor setup.");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getProfessorConfig()
      .then((loaded) => {
        setConfig(loaded);
        setStatus("Professor setup loaded.");
      })
      .catch((error) => setStatus(error instanceof Error ? error.message : "Unable to load setup."));
  }, []);

  async function saveConfig() {
    setBusy(true);
    try {
      const saved = await saveProfessorConfig(config);
      setConfig(saved);
      setStatus("Professor setup saved.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to save setup.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Faculty AI</p>
          <h1>Professor setup</h1>
        </div>
        <Link href="/present">Student presentation mode</Link>
      </header>

      <div className="professor-page">
        <ProfessorConfigForm disabled={busy} value={config} onChange={setConfig} onSave={() => void saveConfig()} />
        <p className="muted">{status}</p>
      </div>
    </main>
  );
}
