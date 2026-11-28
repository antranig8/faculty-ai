"use client";

import { useEffect, useState } from "react";

import { ProfessorConfigForm, type ProfessorConfigDraft } from "@/components/ProfessorConfigForm";
import { RehearsalNav } from "@/components/RehearsalNav";
import styles from "@/components/presentation.module.css";
import { getProfessorConfig, saveProfessorConfig } from "@/lib/api";

const fallbackConfig: ProfessorConfigDraft = {
  courseName: "ENES 104",
  assignmentName: "Project Presentation",
  rubric: "clarity, technical justification, evidence, evaluation, feasibility",
  questionStyle: "skeptical but fair faculty examiner",
  assignmentContext: "",
};

export default function ProfessorPage() {
  const [config, setConfig] = useState(fallbackConfig);
  const [status, setStatus] = useState("Loading professor setup.");
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    getProfessorConfig()
      .then((loaded) => {
        setConfig({ ...loaded, rubric: loaded.rubric.join(", ") });
        setStatus("Professor setup loaded.");
      })
      .catch((error) => setStatus(error instanceof Error ? error.message : "Unable to load setup."))
      .finally(() => setBusy(false));
  }, []);

  async function saveConfig() {
    setBusy(true);
    try {
      const rubric = config.rubric.split(",").map((item) => item.trim()).filter(Boolean);
      const saved = await saveProfessorConfig({ ...config, rubric });
      setConfig({ ...saved, rubric: saved.rubric.join(", ") });
      setStatus("Professor setup saved.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to save setup.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.cockpit}>
      <div className={styles.surface}>
        <RehearsalNav current="professor" />
        <header className={styles.pageHeader}>
          <h1>Professor setup</h1>
          <p className={styles.secondary}>Set the rubric and questioning style for rehearsals.</p>
        </header>
        <div className={styles.details}>
          <ProfessorConfigForm disabled={busy} value={config} onChange={setConfig} onSave={() => void saveConfig()} />
          <p className={`${styles.secondary} ${styles.formStatus}`} role="status">{status}</p>
        </div>
      </div>
    </main>
  );
}
