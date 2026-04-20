"use client";

import type { ProjectContext } from "@/lib/types";

type Props = {
  value: ProjectContext;
  onChange: (value: ProjectContext) => void;
};

function parseList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function ProjectContextForm({ value, onChange }: Props) {
  return (
    <section className="setup-panel">
      <div>
        <p className="eyebrow">Project Context</p>
        <h2>Ground the reviewer before presenting</h2>
      </div>

      <label>
        Project title
        <input
          value={value.title}
          onChange={(event) => onChange({ ...value, title: event.target.value })}
          placeholder="Faculty AI Live Feedback"
        />
      </label>

      <label>
        Summary
        <textarea
          value={value.summary}
          onChange={(event) => onChange({ ...value, summary: event.target.value })}
          placeholder="A live assistant that surfaces faculty-style questions during student presentations."
        />
      </label>

      <label>
        Stack
        <input
          value={value.stack.join(", ")}
          onChange={(event) => onChange({ ...value, stack: parseList(event.target.value) })}
          placeholder="Next.js, FastAPI, OpenAI"
        />
      </label>

      <label>
        Goals
        <textarea
          value={value.goals.join(", ")}
          onChange={(event) => onChange({ ...value, goals: parseList(event.target.value) })}
          placeholder="Generate grounded feedback, avoid spam, support live demos"
        />
      </label>

      <label>
        Rubric criteria
        <textarea
          value={value.rubric.join(", ")}
          onChange={(event) => onChange({ ...value, rubric: parseList(event.target.value) })}
          placeholder="clarity, technical justification, evidence, evaluation, feasibility"
        />
      </label>
    </section>
  );
}
