import styles from "./presentation.module.css";

const micStatusLabels = {
  idle: "Mic off",
  connecting: "Connecting",
  listening: "Listening",
  silent: "Listening · quiet",
  analyzing: "Analyzing",
  error: "Mic error",
};

type Props = {
  liveConnected: boolean;
  liveConnecting: boolean;
  liveStatus: keyof typeof micStatusLabels;
  disabled: boolean;
  voiceEnabled: boolean;
  onStartLive: () => void;
  onStopLive: () => void;
  onToggleVoice: () => void;
};

export function SessionControls({
  liveConnected,
  liveConnecting,
  liveStatus,
  disabled,
  voiceEnabled,
  onStartLive,
  onStopLive,
  onToggleVoice,
}: Props) {
  const running = liveConnected || liveConnecting;

  return (
    <header className={styles.toolbar}>
      <h1>Faculty<span className={styles.brandDash}>–</span>AI</h1>
      <span className={styles.micStatus} data-active={liveConnected} data-error={liveStatus === "error"}>
        {micStatusLabels[liveStatus]}
      </span>
      <div className={`${styles.controls} ${styles.toolbarControls}`}>
        <button onClick={onToggleVoice} type="button" aria-pressed={voiceEnabled}>
          Voice {voiceEnabled ? "on" : "off"}
        </button>
        <button
          className={styles.primary}
          disabled={!running && disabled}
          onClick={running ? onStopLive : onStartLive}
          type="button"
        >
          {running ? "Stop mic" : "Start live mic"}
        </button>
      </div>
    </header>
  );
}
