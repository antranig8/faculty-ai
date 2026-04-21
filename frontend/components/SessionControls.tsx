type Props = {
  running: boolean;
  liveConnected: boolean;
  liveConnecting?: boolean;
  liveStatus?: "idle" | "connecting" | "listening" | "silent" | "analyzing" | "error";
  sessionId?: string;
  disabled?: boolean;
  onStart: () => void;
  onStop: () => void;
  onReset: () => void;
  onNextChunk: () => void;
  onStartLive: () => void;
  onStopLive: () => void;
};

export function SessionControls({
  running,
  liveConnected,
  liveConnecting,
  liveStatus,
  sessionId,
  disabled,
  onStart,
  onStop,
  onReset,
  onNextChunk,
  onStartLive,
  onStopLive,
}: Props) {
  return (
    <section className="session-controls">
      <div>
        <p className="eyebrow">Session</p>
        <h2>{sessionId ? "Presentation mode ready" : "Start a demo session"}</h2>
        <p className="muted">{sessionId ? `Session ${sessionId.slice(0, 8)}` : "Backend session starts when the demo begins."}</p>
        {liveStatus ? <p className="muted">Live state: {liveStatus}</p> : null}
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
        <button
          className="secondary-button"
          disabled={disabled || running || liveConnected || liveConnecting}
          onClick={onStartLive}
          type="button"
        >
          {liveConnecting ? "Connecting mic..." : "Start live mic"}
        </button>
        <button className="secondary-button" disabled={!liveConnected} onClick={onStopLive} type="button">
          Stop live mic
        </button>
        <button onClick={onReset} type="button">
          Reset
        </button>
      </div>
    </section>
  );
}

