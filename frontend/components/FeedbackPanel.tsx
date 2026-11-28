import type { FeedbackItem } from "@/lib/types";

import styles from "./presentation.module.css";

type Props = {
  feedback: FeedbackItem[];
  queuedFeedback?: FeedbackItem;
  onResolve?: (item: FeedbackItem, resolved: boolean) => void;
};

export function FeedbackPanel({ feedback, queuedFeedback, onResolve }: Props) {
  return (
    <>
      {queuedFeedback ? (
        <div className={styles.detailSection}>
          <h3>Queued question</h3>
          <p>{queuedFeedback.message}</p>
          <small className={styles.secondary}>{queuedFeedback.reason}</small>
          {queuedFeedback.targetStudent ? <small className={styles.secondary}>For {queuedFeedback.targetStudent}</small> : null}
        </div>
      ) : null}
      {feedback.length === 0 ? (
        queuedFeedback ? null : <p className={styles.secondary}>Faculty questions will appear here during rehearsal.</p>
      ) : (
        <ul className={`${styles.detailList} ${styles.detailSection}`}>
          {[...feedback].reverse().map((item) => (
            <li key={item.createdAt}>
              <small className={styles.secondary}>
                {item.resolved ? "Addressed" : "Open"}
                {item.followUpToQuestionId ? " · Follow-up" : ""}
                {" · "}{item.type}{" · "}{item.section.replaceAll("_", " ")}
                {item.slideNumber ? ` · Slide ${item.slideNumber}` : ""}
              </small>
              <p>{item.message}</p>
              {item.answerQuality ? <small className={styles.secondary}>Answer quality · {item.answerQuality}</small> : null}
              <details className={styles.secondary}>
                <summary>Question details</summary>
                <p>{item.reason}</p>
                {item.targetStudent ? <p>For {item.targetStudent}</p> : null}
                {item.resolutionReason ? <p>{item.resolutionReason}</p> : null}
              </details>
              {onResolve ? (
                <button onClick={() => onResolve(item, !item.resolved)} type="button">
                  {item.resolved ? "Reopen" : "Mark addressed"}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
