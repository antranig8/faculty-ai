import type { PreparedQuestion, Slide } from "@/lib/types";

import { PresentationUpload } from "./PresentationUpload";
import styles from "./presentation.module.css";

type AudioDiagnostics = {
  socketOpened: number;
  audioChunksSent: number;
  audioBytesSent: number;
  transcriptEvents: number;
  finalChunksAnalyzed: number;
  proxyMessages: number;
  wsCloseEvents: number;
  micTrackEnded: number;
  audioContextState: string;
  lastStopReason: string;
  lastCloseCode?: number;
};

type Props = {
  filename?: string;
  busy: boolean;
  uploadError: string;
  live: boolean;
  sessionId?: string;
  assignmentName: string;
  rubric: string[];
  currentSlide?: Slide;
  preparedQuestions: PreparedQuestion[];
  questionSource?: "llm" | "heuristic";
  questionCacheHit: boolean;
  status: string;
  debugStats: AudioDiagnostics;
  onUpload: (file: File) => void;
  onReset: () => void;
};

export function SessionDetails({
  filename,
  busy,
  uploadError,
  live,
  sessionId,
  assignmentName,
  rubric,
  currentSlide,
  preparedQuestions,
  questionSource,
  questionCacheHit,
  status,
  debugStats,
  onUpload,
  onReset,
}: Props) {
  const currentQuestions = preparedQuestions.filter((question) => question.slideNumber === currentSlide?.slideNumber);

  return (
    <>
      {filename ? (
        <div className={styles.detailSection}>
          <h3>Deck</h3>
          <p>{filename}</p>
          {questionSource ? (
            <small className={styles.secondary}>
              {preparedQuestions.length} prepared questions · {questionSource === "llm" ? "LLM" : "Heuristic"}
              {questionCacheHit ? " · Cached" : ""}
            </small>
          ) : null}
          <div className={styles.controls}>
            <PresentationUpload busy={busy} disabled={live} error={uploadError} replacing onUpload={onUpload} />
            <button onClick={onReset} disabled={busy} type="button">Reset session</button>
          </div>
          {live ? <small className={styles.secondary}>Stop the mic to replace the deck.</small> : null}
        </div>
      ) : null}
      <div className={styles.detailSection}>
        <h3>Rubric</h3>
        <p>{assignmentName}</p>
        {rubric.length > 0 ? <small className={styles.secondary}>{rubric.join(" · ")}</small> : null}
      </div>
      {currentSlide ? (
        <div className={styles.detailSection}>
          <h3>Prepared concerns · Slide {currentSlide.slideNumber}</h3>
          {currentSlide.slideAuthor || currentSlide.slideCategory ? (
            <small className={styles.secondary}>
              {[currentSlide.slideAuthor, currentSlide.slideCategory?.replaceAll("_", " ")].filter(Boolean).join(" · ")}
            </small>
          ) : null}
          {currentQuestions.length > 0 ? (
            <ul className={styles.detailList}>
              {currentQuestions.map((question) => (
                <li key={question.id}>
                  <small className={styles.secondary}>{question.rubricCategory}</small>
                  <p>{question.question}</p>
                </li>
              ))}
            </ul>
          ) : <p className={styles.secondary}>No specific concern prepared for this slide.</p>}
        </div>
      ) : null}
      <details className={styles.diagnostics}>
        <summary>Diagnostics</summary>
        <p className={styles.secondary}>{status}</p>
        {sessionId ? <p className={styles.secondary}>Session {sessionId.slice(0, 8)}</p> : null}
        {debugStats.lastStopReason ? <p className={styles.secondary}>Last stop · {debugStats.lastStopReason}</p> : null}
        <ul className={`${styles.diagnosticList} ${styles.secondary}`}>
          <li>Socket opens {debugStats.socketOpened}</li>
          <li>Audio chunks {debugStats.audioChunksSent}</li>
          <li>Bytes {debugStats.audioBytesSent}</li>
          <li>Transcript events {debugStats.transcriptEvents}</li>
          <li>Analyzed {debugStats.finalChunksAnalyzed}</li>
          <li>Proxy messages {debugStats.proxyMessages}</li>
          <li>Socket closes {debugStats.wsCloseEvents}</li>
          <li>Mic track ends {debugStats.micTrackEnded}</li>
          <li>Audio context {debugStats.audioContextState}</li>
          <li>Last close code {debugStats.lastCloseCode ?? "—"}</li>
        </ul>
      </details>
    </>
  );
}
