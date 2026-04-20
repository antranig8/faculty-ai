import type { FeedbackItem } from "@/lib/types";

const typeLabels: Record<FeedbackItem["type"], string> = {
  question: "Question",
  critique: "Critique",
  suggestion: "Suggestion",
  clarification: "Clarification",
  praise: "Praise",
};

type Props = {
  feedback: FeedbackItem[];
  open: boolean;
  onClose: () => void;
};

export function FeedbackDrawer({ feedback, open, onClose }: Props) {
  return (
    <aside className={`feedback-drawer ${open ? "open" : ""}`} aria-hidden={!open}>
      <div className="drawer-header">
        <div>
          <p className="eyebrow">Faculty Feedback</p>
          <h2>Questions worth pausing for</h2>
        </div>
        <button onClick={onClose} type="button">
          Close
        </button>
      </div>

      <div className="feedback-list">
        {feedback.length === 0 ? (
          <p className="muted">Feedback will appear here when a chunk deserves attention.</p>
        ) : (
          [...feedback].reverse().map((item, index) => (
            <article className={`feedback-card ${item.type}`} key={`${item.createdAt}-${index}`}>
              <div className="feedback-meta">
                <span>{typeLabels[item.type]}</span>
                <span>{item.section.replace("_", " ")}</span>
              </div>
              <p>{item.message}</p>
              <small>{item.reason}</small>
            </article>
          ))
        )}
      </div>
    </aside>
  );
}

