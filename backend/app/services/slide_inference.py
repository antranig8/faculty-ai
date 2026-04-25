import re

from app.models.response_models import Slide

MIN_CONFIDENT_SCORE = 0.18
MIN_SWITCH_SCORE = 0.24
MIN_SWITCH_MARGIN = 0.08
FAR_JUMP_EXTRA_SCORE = 0.06
FAR_JUMP_EXTRA_MARGIN = 0.06


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def infer_current_slide(
    transcript_text: str,
    slides: list[Slide],
    current_slide_number: int | None = None,
) -> Slide | None:
    if not transcript_text or not slides:
        return None

    transcript_tokens = _tokenize(transcript_text)
    if not transcript_tokens:
        return None

    scores: dict[int, float] = {}
    best_slide: Slide | None = None
    best_score = 0.0

    # Score each slide by transcript-token overlap, then bias gently toward the
    # current slide and its immediate neighbors so slide tracking feels stable.
    for slide in slides:
        slide_tokens = _tokenize(f"{slide.title} {slide.content}")
        if not slide_tokens:
            continue

        overlap = len(transcript_tokens & slide_tokens)
        score = overlap / max(1, len(transcript_tokens))

        if current_slide_number == slide.slideNumber:
            score += 0.08
        elif current_slide_number and abs(current_slide_number - slide.slideNumber) == 1:
            score += 0.03

        scores[slide.slideNumber] = score
        if score > best_score:
            best_slide = slide
            best_score = score

    current_slide = next((slide for slide in slides if slide.slideNumber == current_slide_number), None)
    if best_slide is None:
        return current_slide

    # Switching slides requires both a minimum score and a margin over the
    # current slide, with stricter thresholds for larger jumps.
    if current_slide is None:
        return best_slide if best_score >= MIN_CONFIDENT_SCORE else None

    if best_slide.slideNumber == current_slide.slideNumber:
        return best_slide if best_score >= 0.14 else current_slide

    current_score = scores.get(current_slide.slideNumber, 0.0)
    distance = abs(best_slide.slideNumber - current_slide.slideNumber)
    required_score = MIN_SWITCH_SCORE + (FAR_JUMP_EXTRA_SCORE if distance > 1 else 0.0)
    required_margin = MIN_SWITCH_MARGIN + (FAR_JUMP_EXTRA_MARGIN if distance > 1 else 0.0)
    if best_score < required_score or (best_score - current_score) < required_margin:
        return current_slide

    return best_slide
