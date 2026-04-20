import re

from app.models.request_models import ProjectContext
from app.models.response_models import PreparedQuestion, Slide


def parse_slide_outline(slide_outline: str) -> list[Slide]:
    blocks = re.split(r"(?=^slide\s+\d+\s*:)", slide_outline.strip(), flags=re.IGNORECASE | re.MULTILINE)
    slides: list[Slide] = []

    for fallback_index, raw_block in enumerate([block.strip() for block in blocks if block.strip()], start=1):
        lines = [line.strip() for line in raw_block.splitlines() if line.strip()]
        if not lines:
            continue

        header = lines[0]
        match = re.match(r"slide\s+(\d+)\s*:\s*(.*)", header, flags=re.IGNORECASE)
        slide_number = int(match.group(1)) if match else fallback_index
        title = match.group(2).strip() if match and match.group(2).strip() else f"Slide {slide_number}"
        content = "\n".join(lines[1:]) if match else "\n".join(lines)
        slides.append(Slide(slideNumber=slide_number, title=title, content=content))

    if slides:
        return slides

    return [
        Slide(
            slideNumber=1,
            title="Presentation",
            content=slide_outline.strip(),
        )
    ] if slide_outline.strip() else []


def _slide_text(slide: Slide) -> str:
    return f"{slide.title} {slide.content}".lower()


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _rubric_category(project_context: ProjectContext, preferred: str) -> str:
    for item in project_context.rubric:
        if preferred.lower() in item.lower() or item.lower() in preferred.lower():
            return item
    return preferred


def prepare_questions(project_context: ProjectContext, slides: list[Slide]) -> list[PreparedQuestion]:
    prepared: list[PreparedQuestion] = []

    for slide in slides:
        text = _slide_text(slide)
        questions_for_slide: list[PreparedQuestion] = []

        if _has_any(text, ["architecture", "stack", "backend", "frontend", "api", "database", "fastapi", "next.js"]):
            questions_for_slide.append(
                PreparedQuestion(
                    id=f"slide-{slide.slideNumber}-architecture",
                    slideNumber=slide.slideNumber,
                    rubricCategory=_rubric_category(project_context, "technical justification"),
                    type="question",
                    priority="high",
                    question="Why was this architecture the right choice compared with a simpler alternative?",
                    listenFor=["architecture", "stack", "backend", "frontend", "api", "database", "FastAPI", "Next.js"],
                    missingIfAbsent=["because", "alternative", "tradeoff", "chosen", "instead", "compared"],
                )
            )

        if _has_any(text, ["evaluate", "evaluation", "metric", "measure", "result", "outcome", "improve"]):
            questions_for_slide.append(
                PreparedQuestion(
                    id=f"slide-{slide.slideNumber}-evaluation",
                    slideNumber=slide.slideNumber,
                    rubricCategory=_rubric_category(project_context, "evaluation"),
                    type="question",
                    priority="high",
                    question="What metric will show that this project actually works?",
                    listenFor=["evaluate", "metric", "measure", "result", "improve", "outcome", "test"],
                    missingIfAbsent=["metric", "baseline", "compare", "measured", "tested", "survey", "accuracy", "%"],
                )
            )

        if _has_any(text, ["problem", "users", "students", "pain", "need", "challenge"]):
            questions_for_slide.append(
                PreparedQuestion(
                    id=f"slide-{slide.slideNumber}-problem-evidence",
                    slideNumber=slide.slideNumber,
                    rubricCategory=_rubric_category(project_context, "evidence"),
                    type="question",
                    priority="medium",
                    question="What evidence shows this is a real problem for the target users?",
                    listenFor=["problem", "users", "students", "need", "challenge", "pain"],
                    missingIfAbsent=["survey", "interview", "observed", "evidence", "research", "data"],
                )
            )

        if _has_any(text, ["ai", "llm", "model", "personalized", "adaptive", "recommend"]):
            questions_for_slide.append(
                PreparedQuestion(
                    id=f"slide-{slide.slideNumber}-ai-specificity",
                    slideNumber=slide.slideNumber,
                    rubricCategory=_rubric_category(project_context, "clarity"),
                    type="clarification",
                    priority="medium",
                    question="What exactly does the AI decide, and what input does it use to make that decision?",
                    listenFor=["AI", "LLM", "model", "personalized", "adaptive", "recommend"],
                    missingIfAbsent=["input", "output", "decide", "model", "prompt", "data"],
                )
            )

        if not questions_for_slide:
            questions_for_slide.append(
                PreparedQuestion(
                    id=f"slide-{slide.slideNumber}-clarity",
                    slideNumber=slide.slideNumber,
                    rubricCategory=_rubric_category(project_context, "clarity"),
                    type="question",
                    priority="low",
                    question="What is the most important claim faculty should take away from this slide?",
                    listenFor=[slide.title],
                    missingIfAbsent=["because", "evidence", "example", "result"],
                )
            )

        prepared.extend(questions_for_slide[:3])

    return prepared

