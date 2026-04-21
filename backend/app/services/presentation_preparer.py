import re
import json

from groq import Groq

from app.config import get_settings
from app.models.request_models import ProjectContext
from app.models.response_models import PreparedQuestion, Slide
from app.services.prompt_loader import load_prompt
from app.services.rubric_loader import load_professor_config_from_template


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
            # Do not seed generic presenter-facing opener questions for weak slides.
            questions_for_slide = []

        prepared.extend(questions_for_slide[:3])

    return prepared


def _llm_prompt(project_context: ProjectContext, slides: list[Slide]) -> str:
    rubric = load_professor_config_from_template()
    slide_payload = [
        {
            "slideNumber": slide.slideNumber,
            "title": slide.title,
            "content": slide.content,
        }
        for slide in slides[:20]
    ]

    prompt_header = load_prompt(
        "prepared_questions.txt",
        (
            "You are preparing faculty-style questions for a student presentation.\n"
            "Use the rubric and slide content to generate specific, fair questions.\n"
            "Return strict JSON only."
        ),
    )

    return (
        f"{prompt_header}\n\n"
        f"Professor rubric config: {rubric.model_dump_json() if rubric else '{}'}\n"
        f"Project context: {project_context.model_dump_json()}\n"
        f"Slides: {json.dumps(slide_payload)}"
    )


def prepare_questions_with_llm(project_context: ProjectContext, slides: list[Slide]) -> list[PreparedQuestion] | None:
    settings = get_settings()
    if settings.faculty_ai_llm_provider not in {"groq", "openai"}:
        return None
    if not settings.groq_api_key or not slides:
        return None

    client = Groq(api_key=settings.groq_api_key, max_retries=0)
    completion = client.chat.completions.create(
        model=settings.faculty_ai_llm_model,
        messages=[
            {
                "role": "user",
                "content": _llm_prompt(project_context, slides),
            }
        ],
        temperature=0.2,
        max_completion_tokens=1800,
        top_p=1,
        reasoning_effort="medium",
        stream=True,
        stop=None,
    )

    parts: list[str] = []
    for chunk in completion:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            parts.append(delta)

    raw_content = "".join(parts).strip()
    if not raw_content:
        return None

    start = raw_content.find("[")
    end = raw_content.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError("Groq prepared-question response was not valid JSON.")

    try:
        parsed = json.loads(raw_content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("Unable to parse Groq prepared questions JSON.") from exc

    if not isinstance(parsed, list):
        raise RuntimeError("Groq prepared-question response was not an array.")

    prepared: list[PreparedQuestion] = []
    counts_by_slide: dict[int, int] = {}
    valid_slide_numbers = {slide.slideNumber for slide in slides}
    rubric_defaults = project_context.rubric or ["clarity"]

    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue

        slide_number = int(item.get("slideNumber", 0))
        if slide_number not in valid_slide_numbers:
            continue
        if counts_by_slide.get(slide_number, 0) >= 3:
            continue

        question = str(item.get("question", "")).strip()
        if not question:
            continue

        listen_for = [str(value).strip() for value in item.get("listenFor", []) if str(value).strip()]
        missing_if_absent = [str(value).strip() for value in item.get("missingIfAbsent", []) if str(value).strip()]
        rubric_category = str(item.get("rubricCategory", "")).strip() or rubric_defaults[0]
        feedback_type = str(item.get("type", "question")).strip() or "question"
        priority = str(item.get("priority", "medium")).strip() or "medium"

        prepared.append(
            PreparedQuestion(
                id=str(item.get("id", f"slide-{slide_number}-llm-{index + 1}")).strip() or f"slide-{slide_number}-llm-{index + 1}",
                slideNumber=slide_number,
                rubricCategory=rubric_category,
                type=feedback_type,  # validated by Pydantic
                priority=priority,  # validated by Pydantic
                question=question,
                listenFor=listen_for[:8] or [question.split("?")[0][:32]],
                missingIfAbsent=missing_if_absent[:8] or ["because", "evidence", "tradeoff"],
            )
        )
        counts_by_slide[slide_number] = counts_by_slide.get(slide_number, 0) + 1

    return prepared or None

