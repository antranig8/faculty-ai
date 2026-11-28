import styles from "./presentation.module.css";

type Props = {
  transcript: string[];
  activeChunk: string;
  livePreview: string;
};

export function TranscriptPanel({ transcript, activeChunk, livePreview }: Props) {
  return (
    <>
      {livePreview ? (
        <div className={styles.detailSection}>
          <strong className={styles.secondary}>Live preview</strong>
          <p>{livePreview}</p>
        </div>
      ) : null}
      {transcript.length === 0 ? (
        <p className={styles.secondary}>Start the mic to see your transcript here.</p>
      ) : (
        <ol className={`${styles.detailList} ${styles.detailSection}`}>
          {transcript.map((chunk, index) => (
            <li className={index === transcript.length - 1 && chunk === activeChunk ? styles.currentLine : undefined} key={index}>
              {chunk}
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
