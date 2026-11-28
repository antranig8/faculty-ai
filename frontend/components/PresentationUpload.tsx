import styles from "./presentation.module.css";

type Props = {
  disabled?: boolean;
  busy?: boolean;
  replacing?: boolean;
  error?: string;
  onUpload: (file: File) => void;
};

export function PresentationUpload({ disabled, busy, replacing, error, onUpload }: Props) {
  return (
    <div className={styles.upload} aria-busy={busy}>
      <label className={styles.uploadLabel}>
        <span>{busy ? "Preparing slides…" : replacing ? "Replace deck" : "Choose a .pptx"}</span>
        <input
          accept=".pptx"
          disabled={disabled || busy}
          onChange={(event) => {
            const input = event.currentTarget;
            const file = input.files?.[0];
            if (file) {
              onUpload(file);
              input.value = "";
            }
          }}
          type="file"
        />
      </label>
      <small className={styles.secondary}>PowerPoint · 15 MB limit</small>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
    </div>
  );
}
