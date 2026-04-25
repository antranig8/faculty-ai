type Props = {
  liveConnected: boolean;
  liveConnecting?: boolean;
  liveStatus?: "idle" | "connecting" | "listening" | "silent" | "analyzing" | "error";
  sessionId?: string;
  disabled?: boolean;
  voiceEnabled: boolean;
  onReset: () => void;
  onStartLive: () => void;
  onStopLive: () => void;
  onToggleVoice: () => void;
};

export function SessionControls({
  liveConnected,
  liveConnecting,
  liveStatus,
  sessionId,
  disabled,
  voiceEnabled,
  onReset,
  onStartLive,
  onStopLive,
  onToggleVoice,
}: Props) {
  const statusText = liveConnected
    ? "Live mic connected"
    : liveConnecting
      ? "Connecting mic"
      : sessionId
        ? "Session ready"
        : "No active session";

  return (
    <section className="control-panel">
      <div className="control-panel-header">
        <div>
          <p className="eyebrow">Session Control</p>
          <h2>{statusText}</h2>
        </div>
        {liveStatus ? <span className={`status-pill ${liveStatus}`}>{liveStatus}</span> : null}
      </div>

      <p className="control-panel-note">
        Start the live microphone and use the slide tracker to keep faculty context aligned with the deck.
      </p>

      <div className="primary-actions single-action">
        <button
          className="primary-button"
          disabled={disabled || liveConnected || liveConnecting}
          onClick={onStartLive}
          type="button"
        >
          {liveConnecting ? "Connecting..." : "Start live mic"}
        </button>
      </div>

      <div className="secondary-actions">
        <button className="secondary-button" disabled={!liveConnected} onClick={onStopLive} type="button">
          Stop mic
        </button>
        <button className={voiceEnabled ? "secondary-button active-toggle" : "secondary-button"} onClick={onToggleVoice} type="button">
          Voice {voiceEnabled ? "on" : "off"}
        </button>
        <button className="ghost-button" onClick={onReset} type="button">
          Reset
        </button>
      </div>

      {sessionId ? <p className="session-id">Session {sessionId.slice(0, 8)}</p> : null}
    </section>
  );
}

