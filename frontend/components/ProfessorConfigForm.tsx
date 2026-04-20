"use client";

import type { ProfessorConfig } from "@/lib/types";

type Props = {
  value: ProfessorConfig;
  disabled?: boolean;
  onChange: (value: ProfessorConfig) => void;
  onSave: () => void;
};

function parseList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function ProfessorConfigForm({ value, disabled, onChange, onSave }: Props) {
  return (
    <section className="setup-panel professor-form">
      <div>
        <p className="eyebrow">Professor Setup</p>
        <h2>Define how FacultyAI should examine presentations</h2>
      </div>

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
          value={value.rubric.join(", ")}
          onChange={(event) => onChange({ ...value, rubric: parseList(event.target.value) })}
        />
      </label>

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

      <button disabled={disabled} onClick={onSave} type="button">
        Save professor setup
      </button>
    </section>
  );
}

