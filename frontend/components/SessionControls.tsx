type Props = {
  running: boolean;
  sessionId?: string;
  disabled?: boolean;
  onStart: () => void;
  onStop: () => void;
  onReset: () => void;
  onNextChunk: () => void;
};

export function SessionControls({ running, sessionId, disabled, onStart, onStop, onReset, onNextChunk }: Props) {
  return (
    <section className="session-controls">
      <div>
        <p className="eyebrow">Session</p>
        <h2>{sessionId ? "Presentation mode ready" : "Start a demo session"}</h2>
        <p className="muted">{sessionId ? `Session ${sessionId.slice(0, 8)}` : "Backend session starts when the demo begins."}</p>
      </div>

      <div className="button-row">
        <button disabled={disabled || running} onClick={onStart} type="button">
          Start demo
        </button>
        <button disabled={disabled || !sessionId} onClick={onNextChunk} type="button">
          Send next chunk
        </button>
        <button disabled={!running} onClick={onStop} type="button">
          Pause
        </button>
        <button onClick={onReset} type="button">
          Reset
        </button>
      </div>
    </section>
  );
}

