import re
import json

from app.config import get_settings
from app.models.request_models import ProjectContext
from app.models.response_models import PreparedQuestion, Slide
from app.services.groq_client import build_groq_client, groq_reasoning_effort
from app.services.prompt_loader import load_prompt
from app.services.rubric_loader import load_professor_config_from_template

MAX_LLM_SLIDES = 16
MAX_SLIDE_CONTENT_CHARS = 700
PREPARED_QUESTION_MAX_TOKENS = 1400
PREPARED_QUESTION_REPAIR_MAX_TOKENS = 1100


def _clip_text(value: str, limit: int) -> str:
    compacted = " ".join(value.split())
    return compacted if len(compacted) <= limit else f"{compacted[:limit].rstrip()}..."


def parse_slide_outline(slide_outline: str) -> list[Slide]:
    # Accept a loose text outline format for non-file preparation flows and
    # normalize it into the same Slide model used by `.pptx` uploads.
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


def _fallback_question_for_slide(project_context: ProjectContext, slide: Slide) -> PreparedQuestion:
    title = slide.title.strip() or f"slide {slide.slideNumber}"
    return PreparedQuestion(
        id=f"slide-{slide.slideNumber}-slide-specific",
        slideNumber=slide.slideNumber,
        rubricCategory=_rubric_category(project_context, "clarity"),
        type="question",
        priority="medium",
        question=f"What is the strongest claim on {title}, and what specific evidence or example supports it?",
        listenFor=[title, *_clip_text(slide.content, 180).split()[:6]],
        missingIfAbsent=["because", "evidence", "example", "specific", "supports"],
    )


def _is_individual_application_slide(text: str) -> bool:
    return _has_any(text, ["lesson", "lessons", "learned", "apply", "application", "workshop", "speaker", "career", "future"])


def _is_takeaways_slide(text: str) -> bool:
    return _has_any(text, ["takeaway", "takeaways", "lecture", "discussion", "executive summary", "assignment"])


def _is_cip_slide(text: str) -> bool:
    return _has_any(text, ["cip-1", "cip-2", "continuous improvement", "what worked", "could be improved", "management"])


def _individual_application_questions(project_context: ProjectContext, slide: Slide) -> list[PreparedQuestion]:
    return [
        PreparedQuestion(
            id=f"slide-{slide.slideNumber}-individual-application",
            slideNumber=slide.slideNumber,
            rubricCategory=_rubric_category(project_context, "individual application of lessons to future study, career planning, or engineering practice"),
            type="question",
            priority="high",
            question="What changed in this person's view of engineering because of this lesson, and what specific experience caused that change?",
            listenFor=["lesson", "learned", "apply", "application", "workshop", "speaker", "career", "future"],
            missingIfAbsent=["changed", "because", "experience", "speaker", "workshop", "specific example"],
        ),
        PreparedQuestion(
            id=f"slide-{slide.slideNumber}-individual-application-next-step",
            slideNumber=slide.slideNumber,
            rubricCategory=_rubric_category(project_context, "individual application of lessons to future study, career planning, or engineering practice"),
            type="question",
            priority="high",
            question="What concrete decision or behavior will this person change next because of that lesson?",
            listenFor=["lesson", "learned", "apply", "application", "future", "career", "next step"],
            missingIfAbsent=["change", "next", "because", "specific", "future", "decision"],
        ),
    ]


def _max_questions_for_slide(project_context: ProjectContext, slide: Slide) -> int:
    text = _slide_text(slide)
    if _is_individual_application_slide(text) and not _is_takeaways_slide(text) and not _is_cip_slide(text):
        return 2
    return 1


def prepare_questions(project_context: ProjectContext, slides: list[Slide]) -> list[PreparedQuestion]:
    prepared: list[PreparedQuestion] = []
    context_text = " ".join(
        [
            project_context.title,
            project_context.summary,
            project_context.notes or "",
            " ".join(project_context.rubric),
        ]
    ).lower()
    is_assignment6_context = "enes104" in context_text or "enes 104" in context_text or "360" in context_text

    # Deterministic preparation gives every slide at least one usable concern
    # and adds assignment-specific questions for the ENES 104 Assignment 6 flow.
    for slide in slides:
        text = _slide_text(slide)
        questions_for_slide: list[PreparedQuestion] = []
        is_title_like = slide.slideNumber == 1 or (_has_any(text, ["title", "group members"]) and len(text.split()) < 35)

        if is_title_like:
            prepared.extend(questions_for_slide)
            continue

        if is_assignment6_context:
            if _has_any(text, ["cip-2", "team building", "team-building", "teamwork", "team work", "provided each other"]):
                prepared.append(
                    PreparedQuestion(
                        id=f"slide-{slide.slideNumber}-team-feedback",
                        slideNumber=slide.slideNumber,
                        rubricCategory=_rubric_category(project_context, "evidence of feedback exchanged among team members"),
                        type="question",
                        priority="high",
                        question="What is one piece of teammate feedback that actually changed the final presentation, and why did you accept it?",
                        listenFor=["CIP-2", "team building", "teamwork", "feedback", "provided each other", "collaboration"],
                        missingIfAbsent=["feedback", "changed", "accepted", "specific", "because"],
                    )
                )
                continue

            if _has_any(text, ["cip-1", "continuous improvement", "what worked", "could be improved", "management"]):
                prepared.append(
                    PreparedQuestion(
                        id=f"slide-{slide.slideNumber}-course-cip",
                        slideNumber=slide.slideNumber,
                        rubricCategory=_rubric_category(project_context, "continuous improvement plan for ENES 104"),
                        type="question",
                        priority="high",
                        question="If management could only act on one improvement, which one would most change the next ENES 104 student's experience?",
                        listenFor=["CIP-1", "continuous improvement", "worked", "improved", "management", "ENES 104"],
                        missingIfAbsent=["because", "specific", "management", "next student", "priority"],
                    )
                )
                continue

            if _has_any(text, ["takeaway", "takeaways", "lecture", "discussion", "executive summary", "assignment"]):
                prepared.append(
                    PreparedQuestion(
                        id=f"slide-{slide.slideNumber}-team-perspective",
                        slideNumber=slide.slideNumber,
                        rubricCategory=_rubric_category(project_context, "team 360-degree perspective on ENES 104"),
                        type="question",
                        priority="high",
                        question="Where did your team disagree about the most important ENES 104 takeaway, and how did that disagreement shape this slide?",
                        listenFor=["takeaway", "takeaways", "lecture", "discussion", "executive summary", "assignment", "workshop", "speaker series"],
                        missingIfAbsent=["disagree", "different perspectives", "we chose", "because", "most important", "our group"],
                    )
                )
                continue

            if _is_individual_application_slide(text):
                prepared.extend(_individual_application_questions(project_context, slide))
                continue

        if _has_any(text, ["takeaway", "takeaways", "lecture", "discussion", "executive summary", "assignment", "workshop", "speaker series"]):
            questions_for_slide.append(
                PreparedQuestion(
                    id=f"slide-{slide.slideNumber}-team-perspective",
                    slideNumber=slide.slideNumber,
                    rubricCategory=_rubric_category(project_context, "team 360-degree perspective on ENES 104"),
                    type="question",
                    priority="high",
                    question="Where did your team disagree about the most important ENES 104 takeaway, and how did that disagreement shape this slide?",
                    listenFor=["takeaway", "takeaways", "lecture", "discussion", "executive summary", "assignment", "workshop", "speaker series"],
                    missingIfAbsent=["disagree", "different perspectives", "we chose", "because", "most important", "our group"],
                )
            )

        if _is_individual_application_slide(text):
            questions_for_slide.extend(_individual_application_questions(project_context, slide))

        if _has_any(text, ["cip-1", "continuous improvement", "what worked", "could be improved", "management", "enes104", "enes 104"]):
            questions_for_slide.append(
                PreparedQuestion(
                    id=f"slide-{slide.slideNumber}-course-cip",
                    slideNumber=slide.slideNumber,
                    rubricCategory=_rubric_category(project_context, "continuous improvement plan for ENES 104"),
                    type="question",
                    priority="high",
                    question="If management could only act on one improvement, which one would most change the next ENES 104 student's experience?",
                    listenFor=["CIP-1", "continuous improvement", "worked", "improved", "management", "ENES 104"],
                    missingIfAbsent=["because", "specific", "management", "next student", "priority"],
                )
            )

        if _has_any(text, ["cip-2", "team building", "team-building", "teamwork", "team work", "feedback", "provided each other"]):
            questions_for_slide.append(
                PreparedQuestion(
                    id=f"slide-{slide.slideNumber}-team-feedback",
                    slideNumber=slide.slideNumber,
                    rubricCategory=_rubric_category(project_context, "evidence of feedback exchanged among team members"),
                    type="question",
                    priority="high",
                    question="What is one piece of teammate feedback that actually changed the final presentation, and why did you accept it?",
                    listenFor=["CIP-2", "team building", "teamwork", "feedback", "provided each other", "collaboration"],
                    missingIfAbsent=["feedback", "changed", "accepted", "specific", "because"],
                )
            )

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
            questions_for_slide = [_fallback_question_for_slide(project_context, slide)]

        prepared.extend(questions_for_slide[: max(3, _max_questions_for_slide(project_context, slide))])

    return prepared


def _llm_prompt(project_context: ProjectContext, slides: list[Slide]) -> str:
    # The generation prompt is clipped aggressively so large decks can still be
    # prepared within a predictable token budget.
    rubric = load_professor_config_from_template()
    slide_payload = [
        {
            "slideNumber": slide.slideNumber,
            "title": _clip_text(slide.title, 120),
            "content": _clip_text(slide.content, MAX_SLIDE_CONTENT_CHARS),
        }
        for slide in slides[:MAX_LLM_SLIDES]
        if slide.title.strip() or slide.content.strip()
    ]

    prompt_header = load_prompt(
        "prepared_questions.md",
        (
            "You are preparing faculty-style questions for a student presentation.\n"
            "Use the rubric and slide content to generate specific, fair questions.\n"
            "Return strict JSON only."
        ),
    )

    return (
        f"{prompt_header}\n\n"
        f"Professor rubric: {json.dumps({'courseName': rubric.courseName, 'assignmentName': rubric.assignmentName, 'rubric': rubric.rubric[:10], 'questionStyle': rubric.questionStyle, 'assignmentContext': _clip_text(rubric.assignmentContext, 1800)} if rubric else {})}\n"
        f"Project context: {json.dumps({'title': _clip_text(project_context.title, 120), 'summary': _clip_text(project_context.summary, 240), 'rubric': project_context.rubric[:10], 'notes': _clip_text(project_context.notes or '', 600)})}\n"
        f"Slides: {json.dumps(slide_payload)}"
    )


def _extract_json_array(raw_content: str) -> str:
    start = raw_content.find("[")
    if start == -1:
        raise RuntimeError("Groq prepared-question response did not contain a JSON array.")

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(raw_content[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "\"":
                in_string = False
            continue

        if char == "\"":
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return raw_content[start : index + 1]

    raise RuntimeError("Groq prepared-question response contained an incomplete JSON array.")


def _normalize_json_array_text(value: str) -> str:
    # Handles common model slips like trailing commas before object/array close.
    return re.sub(r",\s*([}\]])", r"\1", value.strip())


def _parse_prepared_question_json(raw_content: str) -> list:
    json_text = _normalize_json_array_text(_extract_json_array(raw_content))
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Unable to parse Groq prepared questions JSON.") from exc

    if not isinstance(parsed, list):
        raise RuntimeError("Groq prepared-question response was not an array.")
    return parsed


def _repair_prepared_question_json(client, settings, raw_content: str) -> list | None:
    # When the model returns almost-correct JSON, issue a repair pass instead of
    # throwing away the whole prepared-question response.
    repair_prompt = (
        "Repair this malformed JSON into a valid JSON array only. "
        "Do not add commentary. Preserve the existing fields and values as much as possible. "
        "If an item cannot be repaired, omit only that item.\n\n"
        f"Malformed JSON/text:\n{raw_content[:5000]}"
    )
    completion = client.chat.completions.create(
        model=settings.faculty_ai_llm_model,
        messages=[{"role": "user", "content": repair_prompt}],
        temperature=0,
        max_completion_tokens=PREPARED_QUESTION_REPAIR_MAX_TOKENS,
        top_p=1,
        reasoning_effort=groq_reasoning_effort(settings.faculty_ai_llm_model),
        stream=False,
        stop=None,
    )
    repaired = (completion.choices[0].message.content or "").strip()
    if not repaired:
        return None
    return _parse_prepared_question_json(repaired)


def _coerce_prepared_questions(parsed: list, project_context: ProjectContext, slides: list[Slide]) -> list[PreparedQuestion]:
    # Coerce model output back into the strict PreparedQuestion schema and drop
    # malformed or over-budget items rather than trusting raw provider output.
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
        slide = next((candidate for candidate in slides if candidate.slideNumber == slide_number), None)
        if slide is None:
            continue
        if counts_by_slide.get(slide_number, 0) >= _max_questions_for_slide(project_context, slide):
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
                type=feedback_type,
                priority=priority,
                question=question,
                listenFor=listen_for[:8] or [question.split("?")[0][:32]],
                missingIfAbsent=missing_if_absent[:8] or ["because", "specific", "example"],
            )
        )
        counts_by_slide[slide_number] = counts_by_slide.get(slide_number, 0) + 1

    return prepared


def prepare_questions_with_llm(project_context: ProjectContext, slides: list[Slide]) -> list[PreparedQuestion] | None:
    settings = get_settings()
    if settings.faculty_ai_llm_provider not in {"groq", "openai"}:
        return None
    if not settings.groq_api_key or not slides:
        return None

    # Stream the provider response, parse it as JSON, and repair it once if the
    # model drifts slightly off schema.
    client = build_groq_client(settings.groq_api_key)
    completion = client.chat.completions.create(
        model=settings.faculty_ai_llm_model,
        messages=[
            {
                "role": "user",
                "content": _llm_prompt(project_context, slides),
            }
        ],
        temperature=0.2,
        max_completion_tokens=PREPARED_QUESTION_MAX_TOKENS,
        top_p=1,
        reasoning_effort=groq_reasoning_effort(settings.faculty_ai_llm_model),
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

    try:
        parsed = _parse_prepared_question_json(raw_content)
    except RuntimeError:
        repaired = _repair_prepared_question_json(client, settings, raw_content)
        if repaired is None:
            raise
        parsed = repaired

    return _coerce_prepared_questions(parsed, project_context, slides) or None

