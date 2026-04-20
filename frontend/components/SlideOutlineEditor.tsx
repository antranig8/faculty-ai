type Props = {
  value: string;
  onChange: (value: string) => void;
  onPrepare: () => void;
  disabled?: boolean;
};

export function SlideOutlineEditor({ value, onChange, onPrepare, disabled }: Props) {
  return (
    <section className="setup-panel">
      <div>
        <p className="eyebrow">Slide Outline</p>
        <h2>Prepare faculty questions per slide</h2>
      </div>

      <label>
        Slides
        <textarea
          className="slide-outline-input"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Slide 1: Problem&#10;Students do not get realistic faculty questions before presenting.&#10;&#10;Slide 2: Architecture&#10;Next.js frontend and FastAPI backend."
        />
      </label>

      <button disabled={disabled} onClick={onPrepare} type="button">
        Prepare questions
      </button>
    </section>
  );
}

