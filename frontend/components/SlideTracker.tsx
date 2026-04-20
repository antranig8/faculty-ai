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
  const slideQuestions = currentSlide
    ? preparedQuestions.filter((question) => question.slideNumber === currentSlide.slideNumber)
    : [];

  return (
    <section className="slide-tracker">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Current Slide</p>
          <h2>{currentSlide ? `Slide ${currentSlide.slideNumber}: ${currentSlide.title}` : "No prepared slides"}</h2>
        </div>
        <span>{slides.length ? `${currentSlideIndex + 1} of ${slides.length}` : "0 slides"}</span>
      </div>

      {currentSlide ? <p className="slide-copy">{currentSlide.content || "No slide notes provided."}</p> : null}

      <div className="button-row">
        <button disabled={currentSlideIndex <= 0} onClick={onPrevious} type="button">
          Previous slide
        </button>
        <button disabled={currentSlideIndex >= slides.length - 1} onClick={onNext} type="button">
          Next slide
        </button>
      </div>

      <div className="prepared-question-list">
        <p className="eyebrow">Prepared faculty concerns</p>
        {slideQuestions.length === 0 ? (
          <p className="muted">Prepare the presentation to load slide-specific questions.</p>
        ) : (
          slideQuestions.map((question) => (
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
