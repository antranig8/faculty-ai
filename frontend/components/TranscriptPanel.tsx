type Props = {
  transcript: string[];
  activeChunk: string;
};

export function TranscriptPanel({ transcript, activeChunk }: Props) {
  return (
    <section className="transcript-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Live Transcript</p>
          <h2>Presenter audio stream</h2>
        </div>
        <span>{transcript.length} chunks</span>
      </div>

      <div className="transcript-body">
        {transcript.length === 0 ? (
          <p className="muted">Start the demo to send transcript chunks for analysis.</p>
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

