import type { FeedbackItem } from "@/lib/types";

import { ProfessorCutout } from "./ProfessorCutout";
import cutout from "./FacultyQuestion.module.css";
import styles from "./presentation.module.css";

type Props = {
  question: FeedbackItem;
  animate: boolean;
  rephrasedQuestion?: string;
  rephrasing: boolean;
  voiceEnabled: boolean;
  onRepeat: () => void;
  onRephrase: () => void;
  onResolve: () => void;
};

export function FacultyQuestion({
  question,
  animate,
  rephrasedQuestion,
  rephrasing,
  voiceEnabled,
  onRepeat,
  onRephrase,
  onResolve,
}: Props) {
  return (
    <article
      className={animate ? `${cutout.question} ${cutout.enter}` : cutout.question}
      aria-label="Current faculty question"
    >
      <ProfessorCutout />
      <div className={styles.questionBody}>
        <p className={styles.questionLabel}>
          {question.followUpToQuestionId ? "Faculty follow-up" : "Faculty question"}
        </p>
        <h3 className={styles.questionText}>{rephrasedQuestion ?? question.message}</h3>
        {question.targetStudent ? <small className={styles.secondary}>For {question.targetStudent}</small> : null}
        <div className={`${styles.controls} ${styles.questionActions}`}>
          <button onClick={onRepeat} disabled={!voiceEnabled} type="button">Repeat</button>
          <button onClick={onRephrase} disabled={rephrasing} type="button">{rephrasing ? "Rephrasing…" : "Rephrase"}</button>
          <button onClick={onResolve} type="button">Mark addressed</button>
        </div>
      </div>
    </article>
  );
}
