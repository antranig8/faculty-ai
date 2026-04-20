type Props = {
  disabled?: boolean;
  filename?: string;
  onUpload: (file: File) => void;
};

export function PresentationUpload({ disabled, filename, onUpload }: Props) {
  return (
    <section className="setup-panel">
      <div>
        <p className="eyebrow">Student Upload</p>
        <h2>Upload the presentation deck</h2>
      </div>

      <label>
        PowerPoint file
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
      </label>

      <p className="muted">{filename ? `Loaded ${filename}` : "Only .pptx is supported in this build."}</p>
    </section>
  );
}

