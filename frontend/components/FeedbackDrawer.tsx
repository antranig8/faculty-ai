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
  latestFeedback?: FeedbackItem;
  onClose: () => void;
};

export function FeedbackDrawer({ feedback, open, latestFeedback, onClose }: Props) {
  const visibleFeedback = latestFeedback ? [...feedback].reverse().slice(1) : [...feedback].reverse();

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

      {latestFeedback ? (
        <section className="live-feedback-preview">
          <p className="eyebrow">Live Faculty Question</p>
          <h3>{latestFeedback.message}</h3>
          <p className="muted">{latestFeedback.reason}</p>
        </section>
      ) : null}

      <div className="feedback-list">
        {feedback.length === 0 ? (
          <p className="muted">Feedback will appear here when a chunk deserves attention.</p>
        ) : visibleFeedback.length === 0 ? (
          <p className="muted">The latest faculty question is shown above.</p>
        ) : (
          visibleFeedback.map((item, index) => (
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

