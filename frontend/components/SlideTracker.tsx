import type { ReactNode } from "react";

import type { Slide } from "@/lib/types";

import styles from "./presentation.module.css";

type Props = {
  slides: Slide[];
  currentSlideIndex: number;
  slideMode: "auto" | "manual";
  caption: string;
  onModeChange: (mode: "auto" | "manual") => void;
  onJumpToSlide: (slideNumber: number) => void;
  children?: ReactNode;
};

export function SlideTracker({
  slides,
  currentSlideIndex,
  slideMode,
  caption,
  onModeChange,
  onJumpToSlide,
  children,
}: Props) {
  const slide = slides[currentSlideIndex];
  if (!slide) {
    return null;
  }

  return (
    <section className={styles.stage} aria-label="Current slide">
      <div className={styles.slideToolbar}>
        <select
          aria-label="Jump to slide"
          value={slide.slideNumber}
          onChange={(event) => onJumpToSlide(Number(event.target.value))}
        >
          {slides.map((entry, index) => (
            <option key={entry.slideNumber} value={entry.slideNumber}>
              {index === currentSlideIndex ? `Slide ${index + 1} of ${slides.length}` : `${index + 1}. ${entry.title || "Untitled"}`}
            </option>
          ))}
        </select>
        <button
          aria-pressed={slideMode === "auto"}
          onClick={() => onModeChange(slideMode === "auto" ? "manual" : "auto")}
          type="button"
        >
          {slideMode === "auto" ? "Auto follow" : "Manual lock"}
        </button>
      </div>
      <div className={styles.slideContent}>
        <h2>{slide.title || `Slide ${slide.slideNumber}`}</h2>
        {caption ? <p className={styles.caption}>{caption}</p> : null}
      </div>
      {children}
    </section>
  );
}
