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
  queuedFeedback?: FeedbackItem;
  open: boolean;
  latestFeedback?: FeedbackItem;
  latestFeedbackRephrase?: string;
  onClose: () => void;
  onResolve: (item: FeedbackItem, resolved: boolean) => void;
};

function uniqueFeedbackItems(items: FeedbackItem[]): FeedbackItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = item.sourceQuestionId ?? item.message.trim().toLowerCase();
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

export function FeedbackDrawer({ feedback, queuedFeedback, open, latestFeedback, latestFeedbackRephrase, onClose, onResolve }: Props) {
  const visibleFeedback = uniqueFeedbackItems(
    latestFeedback
      ? [...feedback].reverse().filter((item) => item.createdAt !== latestFeedback.createdAt)
      : [...feedback].reverse(),
  );

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
        <section className={`live-feedback-preview ${latestFeedback.resolved ? "resolved" : ""}`}>
          <div className="feedback-meta">
            <span>Live Faculty Question</span>
            <span>{latestFeedback.section.replace("_", " ")}</span>
          </div>
          <h3>{latestFeedback.message}</h3>
          {latestFeedbackRephrase ? <small>Rephrased: {latestFeedbackRephrase}</small> : null}
          {latestFeedback.targetStudent ? <small>Targeted student: {latestFeedback.targetStudent}</small> : null}
          <small>{latestFeedback.reason}</small>
          <button className="resolved-button" onClick={() => onResolve(latestFeedback, true)} type="button">
            Mark addressed
          </button>
        </section>
      ) : null}

      {queuedFeedback ? (
        <section className="live-feedback-preview">
          <div className="feedback-meta">
            <span>Queued Faculty Question</span>
            <span>{queuedFeedback.section.replace("_", " ")}</span>
          </div>
          <h3>{queuedFeedback.message}</h3>
          {queuedFeedback.targetStudent ? <small>Targeted student: {queuedFeedback.targetStudent}</small> : null}
          <small>{queuedFeedback.reason}</small>
        </section>
      ) : null}

      <div className="feedback-list">
        {feedback.length === 0 ? (
          <p className="muted">Feedback will appear here when a chunk deserves attention.</p>
        ) : visibleFeedback.length === 0 ? (
          <p className="muted">The latest faculty question is shown above.</p>
        ) : (
          visibleFeedback.map((item, index) => (
            <article className={`feedback-card ${item.type} ${item.resolved ? "resolved" : ""}`} key={`${item.createdAt}-${index}`}>
              <div className="feedback-meta">
                <span>{typeLabels[item.type]}</span>
                <span>{item.resolved ? "addressed" : item.section.replace("_", " ")}</span>
              </div>
              <p>{item.message}</p>
              {item.targetStudent ? <small>Targeted student: {item.targetStudent}</small> : null}
              <small>{item.reason}</small>
              {item.answerQuality ? <small>Answer quality: {item.answerQuality}</small> : null}
              {item.followUpToQuestionId ? <small>Follow-up to earlier faculty question.</small> : null}
              {item.resolved ? (
                <>
                  <small>{item.resolutionReason ?? "Marked addressed."}</small>
                  <button className="secondary-button" onClick={() => onResolve(item, false)} type="button">
                    Reopen
                  </button>
                </>
              ) : null}
            </article>
          ))
        )}
      </div>
    </aside>
  );
}

