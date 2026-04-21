type Props = {
  running: boolean;
  liveConnected: boolean;
  liveConnecting?: boolean;
  liveStatus?: "idle" | "connecting" | "listening" | "silent" | "analyzing" | "error";
  canFinalize?: boolean;
  sessionId?: string;
  disabled?: boolean;
  onStart: () => void;
  onStop: () => void;
  onReset: () => void;
  onNextChunk: () => void;
  onStartLive: () => void;
  onStopLive: () => void;
  onFinalize: () => void;
};

export function SessionControls({
  running,
  liveConnected,
  liveConnecting,
  liveStatus,
  canFinalize,
  sessionId,
  disabled,
  onStart,
  onStop,
  onReset,
  onNextChunk,
  onStartLive,
  onStopLive,
  onFinalize,
}: Props) {
  const statusText = liveConnected
    ? "Live mic connected"
    : liveConnecting
      ? "Connecting mic"
      : running
        ? "Demo running"
        : sessionId
          ? "Session ready"
          : "No active session";

  return (
    <section className="control-panel">
      <div className="control-panel-header">
        <div>
          <p className="eyebrow">Run</p>
          <h2>{statusText}</h2>
        </div>
        {liveStatus ? <span className={`status-pill ${liveStatus}`}>{liveStatus}</span> : null}
      </div>

      <div className="primary-actions">
        <button
          className="primary-button"
          disabled={disabled || running || liveConnected || liveConnecting}
          onClick={onStartLive}
          type="button"
        >
          {liveConnecting ? "Connecting..." : "Start live mic"}
        </button>
        <button disabled={disabled || running || liveConnected || liveConnecting} onClick={onStart} type="button">
          Start demo
        </button>
      </div>

      <div className="secondary-actions">
        <button disabled={disabled || !sessionId || liveConnected} onClick={onNextChunk} type="button">
          Next demo chunk
        </button>
        <button disabled={!running} onClick={onStop} type="button">
          Pause demo
        </button>
        <button className="secondary-button" disabled={!liveConnected} onClick={onStopLive} type="button">
          Stop mic
        </button>
        <button className="secondary-button" disabled={disabled || !canFinalize} onClick={onFinalize} type="button">
          Finalize
        </button>
        <button className="ghost-button" onClick={onReset} type="button">
          Reset
        </button>
      </div>

      {sessionId ? <p className="session-id">Session {sessionId.slice(0, 8)}</p> : null}
    </section>
  );
}

