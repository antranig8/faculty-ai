type Props = {
  transcript: string[];
  activeChunk: string;
  livePreview?: string;
  liveStatus?: "idle" | "connecting" | "listening" | "silent" | "analyzing" | "error";
  debugStats?: {
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
};

const liveStatusLabel: Record<NonNullable<Props["liveStatus"]>, string> = {
  idle: "Idle",
  connecting: "Connecting",
  listening: "Listening",
  silent: "Waiting",
  analyzing: "Analyzing",
  error: "Error",
};

export function TranscriptPanel({ transcript, activeChunk, livePreview = "", liveStatus = "idle", debugStats }: Props) {
  return (
    <section className="transcript-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Live Transcript</p>
          <h2>Presenter audio stream</h2>
          <p className="muted transcript-subtitle">Watch live speech, chunk timing, and diagnostics in one place.</p>
        </div>
        <div className="transcript-status">
          <span className={`status-pill ${liveStatus}`}>{liveStatusLabel[liveStatus]}</span>
          <span>{transcript.length} chunks</span>
        </div>
      </div>

      {debugStats ? (
        <details className="transcript-debug">
          <summary>Diagnostics</summary>
          <div>
            <span>socket {debugStats.socketOpened}</span>
            <span>audio {debugStats.audioChunksSent}</span>
            <span>bytes {debugStats.audioBytesSent}</span>
            <span>events {debugStats.transcriptEvents}</span>
            <span>analyzed {debugStats.finalChunksAnalyzed}</span>
            <span>proxy {debugStats.proxyMessages}</span>
            <span>wsclose {debugStats.wsCloseEvents}</span>
            <span>trackend {debugStats.micTrackEnded}</span>
            <span>audioctx {debugStats.audioContextState}</span>
            <span>close {debugStats.lastCloseCode ?? "-"}</span>
          </div>
        </details>
      ) : null}

      {debugStats?.lastStopReason ? <p className="transcript-note">Last stop: {debugStats.lastStopReason}</p> : null}

      {livePreview ? (
        <div className="live-preview">
          <span>Live preview</span>
          <p>{livePreview}</p>
        </div>
      ) : null}

      <div className="transcript-body">
        {transcript.length === 0 ? (
          <p className="muted">Start live mic or demo mode to send transcript chunks for analysis.</p>
        ) : (
          transcript.map((chunk, index) => (
            <p className={chunk === activeChunk ? "active-line" : ""} key={`${chunk}-${index}`}>
              {chunk}
            </p>
          ))
        )}
      </div>
    </section>
  );
}

