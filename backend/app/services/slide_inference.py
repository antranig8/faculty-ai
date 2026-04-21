import re

from app.models.response_models import Slide


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

    best_slide: Slide | None = None
    best_score = 0.0

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

        if score > best_score:
            best_slide = slide
            best_score = score

    if best_score < 0.12:
        return next((slide for slide in slides if slide.slideNumber == current_slide_number), None)

    return best_slide
