"use client";

import type { ProfessorConfig } from "@/lib/types";

import styles from "./presentation.module.css";

export type ProfessorConfigDraft = Omit<ProfessorConfig, "rubric"> & { rubric: string };

type Props = {
  value: ProfessorConfigDraft;
  disabled?: boolean;
  onChange: (value: ProfessorConfigDraft) => void;
  onSave: () => void;
};

export function ProfessorConfigForm({ value, disabled, onChange, onSave }: Props) {
  return (
    <form onSubmit={(event) => { event.preventDefault(); onSave(); }}>
      <fieldset className={styles.professorFields} disabled={disabled}>
        <label>
          Course
          <input value={value.courseName} onChange={(event) => onChange({ ...value, courseName: event.target.value })} />
        </label>

        <label>
          Assignment
          <input
            value={value.assignmentName}
            onChange={(event) => onChange({ ...value, assignmentName: event.target.value })}
          />
        </label>

        <label>
          Rubric criteria
          <textarea
            aria-describedby="rubric-format"
            value={value.rubric}
            onChange={(event) => onChange({ ...value, rubric: event.target.value })}
          />
        </label>
        <small id="rubric-format" className={styles.secondary}>Separate criteria with commas.</small>

        <label>
          Faculty style
          <input
            value={value.questionStyle}
            onChange={(event) => onChange({ ...value, questionStyle: event.target.value })}
          />
        </label>

        <label>
          Assignment context
          <textarea
            value={value.assignmentContext}
            onChange={(event) => onChange({ ...value, assignmentContext: event.target.value })}
          />
        </label>

        <button className={styles.primary} type="submit">
          Save professor setup
        </button>
      </fieldset>
    </form>
  );
}

