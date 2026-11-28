import { useRef, useState, type DragEvent } from "react";

import styles from "./presentation.module.css";

type Props = {
  disabled?: boolean;
  busy?: boolean;
  replacing?: boolean;
  error?: string;
  onUpload: (file: File) => void;
};

export function PresentationUpload({ disabled, busy, replacing, error, onUpload }: Props) {
  const dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);
  const [fileError, setFileError] = useState("");
  const unavailable = disabled || busy;
  const uploadError = fileError || error;

  function acceptFiles(files: FileList) {
    if (unavailable || files.length === 0) {
      return;
    }
    if (files.length !== 1 || !files[0].name.toLowerCase().endsWith(".pptx")) {
      setFileError("Choose one PowerPoint (.pptx) file.");
      return;
    }
    setFileError("");
    onUpload(files[0]);
  }

  function onDragEnter(event: DragEvent<HTMLDivElement>) {
    if (!event.dataTransfer.types.includes("Files")) {
      return;
    }
    event.preventDefault();
    dragDepth.current += 1;
    setDragging(true);
  }

  function onDragLeave() {
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) {
      setDragging(false);
    }
  }

  function onDragOver(event: DragEvent<HTMLDivElement>) {
    if (event.dataTransfer.types.includes("Files")) {
      event.preventDefault();
      event.dataTransfer.dropEffect = unavailable ? "none" : "copy";
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    if (!event.dataTransfer.types.includes("Files")) {
      return;
    }
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    acceptFiles(event.dataTransfer.files);
  }

  return (
    <div
      className={replacing ? styles.upload : `${styles.upload} ${styles.slideContent} ${styles.emptyStage}`}
      aria-busy={busy}
      data-dragging={dragging && !unavailable}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      {replacing ? null : <h2 id="upload-deck-heading">Upload your deck</h2>}
      <label className={styles.uploadLabel}>
        <span>{busy ? "Preparing slides…" : replacing ? "Replace deck" : "Choose a .pptx"}</span>
        <input
          accept=".pptx"
          disabled={unavailable}
          onChange={(event) => {
            const input = event.currentTarget;
            if (input.files) {
              acceptFiles(input.files);
            }
            input.value = "";
          }}
          type="file"
        />
      </label>
      <small className={styles.secondary}>
        {unavailable ? "PowerPoint" : "Or drop a .pptx here"} · 15 MB limit
      </small>
      {uploadError ? <p className={styles.error} role="alert">{uploadError}</p> : null}
    </div>
  );
}
