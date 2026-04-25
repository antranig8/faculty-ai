type Props = {
  disabled?: boolean;
  filename?: string;
  onUpload: (file: File) => void;
};

export function PresentationUpload({ disabled, filename, onUpload }: Props) {
  return (
    <section className="deck-card">
      <div className="deck-card-header">
        <p className="eyebrow">Deck</p>
        <h2>{filename ? filename : "Upload slides"}</h2>
        <p className="muted">{filename ? "Prepared concerns stay attached to this deck during the session." : "Upload the deck first so slide-aware questions are ready before the talk starts."}</p>
      </div>

      <label className="file-picker">
        <input
          accept=".pptx"
          disabled={disabled}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) {
              onUpload(file);
            }
          }}
          type="file"
        />
        <span>{filename ? "Replace deck" : "Choose .pptx"}</span>
      </label>
      <div className="deck-card-meta">
        <span>Format: .pptx</span>
        <span>Limit: 15 MB</span>
      </div>
    </section>
  );
}

