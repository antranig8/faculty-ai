import json
from datetime import timezone

from pydantic import ValidationError

from app.config import get_settings
from app.models.request_models import AnalyzeChunkRequest
from app.models.response_models import FeedbackItem
from app.services.cooldown import utc_now
from app.services.groq_client import build_groq_client, groq_reasoning_effort
from app.services.prompt_loader import load_prompt
from app.services.rubric_loader import load_professor_config_from_template
from app.services.section_tracker import infer_section
from app.services.transcript_evidence import extract_transcript_evidence

LIVE_FALLBACK_MAX_COMPLETION_TOKENS = 160
MAX_PROMPT_TEXT_CHARS = 220


def _created_at() -> str:
    return utc_now().astimezone(timezone.utc).isoformat()


def _clip_text(value: str, limit: int = MAX_PROMPT_TEXT_CHARS) -> str:
    compacted = " ".join(value.split())
    return compacted if len(compacted) <= limit else f"{compacted[:limit].rstrip()}..."


def _clip_list(items: list[str], count: int = 3, char_limit: int = 100) -> list[str]:
    return [_clip_text(item, char_limit) for item in items if item][:count]


def _build_prompt(payload: AnalyzeChunkRequest) -> str:
    rubric = load_professor_config_from_template()
    transcript_evidence = extract_transcript_evidence(payload.recentTranscript, payload.transcriptChunk)
    slide_summary = "none"
    if payload.currentSlide:
        slide_summary = json.dumps(
            {
                "slideNumber": payload.currentSlide.slideNumber,
                "title": _clip_text(payload.currentSlide.title, 120),
                "content": _clip_text(payload.currentSlide.content, 320),
            }
        )

    prepared_questions = [
        {
            "slideNumber": item.slideNumber,
            "rubricCategory": item.rubricCategory,
            "type": item.type,
            "priority": item.priority,
            "question": _clip_text(item.question, 140),
            "listenFor": _clip_list(item.listenFor, 4, 40),
            "missingIfAbsent": _clip_list(item.missingIfAbsent, 4, 50),
        }
        for item in payload.preparedQuestions[:2]
    ]

    prompt_header = load_prompt(
        "interrupt_fallback.md",
        (
            "You are FacultyAI, a skeptical but fair faculty examiner during a student project presentation.\n"
            "Decide whether the latest transcript chunk merits one concise faculty interruption.\n"
            "Return strict JSON only."
        ),
    )

    return (
        f"{prompt_header}\n\n"
        f"Transcript chunk count so far: {len(payload.recentTranscript) + 1}\n"
        f"Professor rubric: {json.dumps({'courseName': rubric.courseName, 'assignmentName': rubric.assignmentName, 'rubric': rubric.rubric[:6]} if rubric else {})}\n"
        f"Project context: {json.dumps({'title': _clip_text(payload.projectContext.title, 120), 'rubric': payload.projectContext.rubric[:6]})}\n"
        f"Current slide: {slide_summary}\n"
        f"Transcript evidence: {json.dumps({'summary': _clip_text(transcript_evidence.summary, 180), 'claims': _clip_list(transcript_evidence.claims, 2, 100), 'technicalChoices': _clip_list(transcript_evidence.technicalChoices, 2, 100), 'metrics': transcript_evidence.metrics[:3], 'unansweredGaps': _clip_list(transcript_evidence.unansweredGaps, 3, 100)})}\n"
        f"Prepared questions: {json.dumps(prepared_questions)}\n"
        f"Recent transcript: {json.dumps(_clip_list(payload.recentTranscript[-2:], 2, 160))}\n"
        f"Recent feedback: {json.dumps(_clip_list(payload.recentFeedback[-1:], 1, 120))}\n"
        f"Latest transcript chunk: {json.dumps(_clip_text(payload.transcriptChunk, 220))}"
    )


def generate_llm_feedback(payload: AnalyzeChunkRequest) -> tuple[FeedbackItem | None, str] | None:
    settings = get_settings()
    if settings.faculty_ai_llm_provider not in {"groq", "openai"}:
        return None
    if not settings.groq_api_key:
        return None

    client = build_groq_client(settings.groq_api_key)
    completion = client.chat.completions.create(
        model=settings.faculty_ai_llm_model,
        messages=[
            {
                "role": "user",
                "content": _build_prompt(payload),
            }
        ],
        temperature=0.2,
        max_completion_tokens=LIVE_FALLBACK_MAX_COMPLETION_TOKENS,
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

    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError("Groq response was not valid JSON.")

    try:
        parsed = json.loads(raw_content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("Unable to parse Groq JSON response.") from exc

    if not parsed.get("trigger"):
        return None, parsed.get("reason", "LLM declined to interrupt.")

    feedback_payload = parsed.get("feedback")
    if not isinstance(feedback_payload, dict):
        raise RuntimeError("Groq returned trigger=true without feedback.")

    section = infer_section(" ".join([*payload.recentTranscript[-4:], payload.transcriptChunk]))
    try:
        feedback = FeedbackItem(
            type=feedback_payload["type"],
            priority=feedback_payload["priority"],
            section=section,
            message=str(feedback_payload["message"]).strip(),
            reason=parsed.get("reason", "Generated by Groq faculty reasoning."),
            createdAt=_created_at(),
        )
    except (KeyError, ValidationError) as exc:
        raise RuntimeError("Groq returned feedback in an invalid shape.") from exc

    return feedback, parsed.get("reason", "Generated by Groq faculty reasoning.")
