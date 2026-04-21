import type { PreparedQuestion, Slide } from "@/lib/types";

type Props = {
  slides: Slide[];
  preparedQuestions: PreparedQuestion[];
  currentSlideIndex: number;
  onPrevious: () => void;
  onNext: () => void;
};

export function SlideTracker({ slides, preparedQuestions, currentSlideIndex, onPrevious, onNext }: Props) {
  const currentSlide = slides[currentSlideIndex];
  const currentQuestions = currentSlide
    ? preparedQuestions.filter((question) => question.slideNumber === currentSlide.slideNumber)
    : [];

  return (
    <section className="slide-tracker-compact">
      <div className="slide-tracker-top">
        <div>
          <p className="eyebrow">Slide Tracker</p>
          <h2>{currentSlide ? `Slide ${currentSlide.slideNumber}` : "No slide selected"}</h2>
          <p className="muted">{currentSlide ? currentSlide.title || "Untitled slide" : "Upload a deck to prepare tracking."}</p>
        </div>
        <span>{slides.length ? `${currentSlideIndex + 1} / ${slides.length}` : "0 / 0"}</span>
      </div>

      <div className="slide-controls">
        <button disabled={currentSlideIndex <= 0} onClick={onPrevious} type="button">
          Previous
        </button>
        <button disabled={currentSlideIndex >= slides.length - 1} onClick={onNext} type="button">
          Next
        </button>
      </div>

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
