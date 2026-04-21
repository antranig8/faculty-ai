type Props = {
  disabled?: boolean;
  filename?: string;
  onUpload: (file: File) => void;
};

export function PresentationUpload({ disabled, filename, onUpload }: Props) {
  return (
    <section className="deck-card">
      <div>
        <p className="eyebrow">Deck</p>
        <h2>{filename ? filename : "Upload slides"}</h2>
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

      <p className="muted">{filename ? "Questions are prepared from this deck." : "PowerPoint only, up to 15 MB."}</p>
    </section>
  );
}

