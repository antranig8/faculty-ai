import type { PreparedQuestion, Slide } from "@/lib/types";

type SlideMode = "auto" | "manual";

type Props = {
  slides: Slide[];
  preparedQuestions: PreparedQuestion[];
  currentSlideIndex: number;
  slideMode: SlideMode;
  onModeChange: (mode: SlideMode) => void;
  onJumpToSlide: (slideNumber: number) => void;
  onPrevious: () => void;
  onNext: () => void;
};

export function SlideTracker({
  slides,
  preparedQuestions,
  currentSlideIndex,
  slideMode,
  onModeChange,
  onJumpToSlide,
  onPrevious,
  onNext,
}: Props) {
  const currentSlide = slides[currentSlideIndex];
  const currentQuestions = currentSlide
    ? preparedQuestions.filter((question) => question.slideNumber === currentSlide.slideNumber)
    : [];
  const categoryLabel = currentSlide?.slideCategory ? currentSlide.slideCategory.replaceAll("_", " ") : "unknown";

  return (
    <section className="slide-tracker-compact">
      <div className="slide-tracker-top">
        <div>
          <p className="eyebrow">Slide Tracker</p>
          <h2>{currentSlide ? `Slide ${currentSlide.slideNumber}` : "No slide selected"}</h2>
          <p className="muted">{currentSlide ? currentSlide.title || "Untitled slide" : "Upload a deck to prepare tracking."}</p>
          {currentSlide ? (
            <p className="muted">
              {categoryLabel}
              {currentSlide.slideAuthor ? ` · ${currentSlide.slideAuthor}` : ""}
            </p>
          ) : null}
        </div>
        <div className="slide-tracker-badges">
          <span>{slides.length ? `${currentSlideIndex + 1} / ${slides.length}` : "0 / 0"}</span>
          <span className={`mode-badge ${slideMode}`}>{slideMode === "manual" ? "Manual lock" : "Auto follow"}</span>
        </div>
      </div>

      <div className="mode-switcher" role="tablist" aria-label="Slide tracking mode">
        <button
          className={slideMode === "manual" ? "mode-button active" : "mode-button"}
          onClick={() => onModeChange("manual")}
          type="button"
        >
          Manual
        </button>
        <button
          className={slideMode === "auto" ? "mode-button active" : "mode-button"}
          onClick={() => onModeChange("auto")}
          type="button"
        >
          Auto
        </button>
      </div>

      <div className="slide-controls">
        <button disabled={currentSlideIndex <= 0} onClick={onPrevious} type="button">
          Previous
        </button>
        <button disabled={currentSlideIndex >= slides.length - 1} onClick={onNext} type="button">
          Next
        </button>
      </div>

      {slides.length > 0 ? (
        <div className="slide-chip-strip" aria-label="Slide jump controls">
          {slides.map((slide, index) => (
            <button
              key={slide.slideNumber}
              className={index === currentSlideIndex ? "slide-chip active" : "slide-chip"}
              onClick={() => onJumpToSlide(slide.slideNumber)}
              type="button"
            >
              <span>Slide {slide.slideNumber}</span>
              <strong>{slide.title || "Untitled"}</strong>
            </button>
          ))}
        </div>
      ) : null}

      <div className="current-concerns">
        <div className="concern-header">
          <p className="eyebrow">Prepared Concerns</p>
          <span>{currentQuestions.length}</span>
        </div>

        {currentQuestions.length === 0 ? (
          <p className="muted">No specific concern prepared for this slide.</p>
        ) : (
          currentQuestions.map((question) => (
            <article key={question.id}>
              <strong>{question.rubricCategory}</strong>
              <p>{question.question}</p>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
