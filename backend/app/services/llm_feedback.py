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

LIVE_FALLBACK_MAX_COMPLETION_TOKENS = 220


def _created_at() -> str:
    return utc_now().astimezone(timezone.utc).isoformat()


def _build_prompt(payload: AnalyzeChunkRequest) -> str:
    rubric = load_professor_config_from_template()
    transcript_evidence = extract_transcript_evidence(payload.recentTranscript, payload.transcriptChunk)
    slide_summary = "none"
    if payload.currentSlide:
        slide_summary = json.dumps(
            {
                "slideNumber": payload.currentSlide.slideNumber,
                "title": payload.currentSlide.title,
                "content": payload.currentSlide.content,
            }
        )

    prepared_questions = [
        {
            "slideNumber": item.slideNumber,
            "rubricCategory": item.rubricCategory,
            "type": item.type,
            "priority": item.priority,
            "question": item.question,
            "listenFor": item.listenFor,
            "missingIfAbsent": item.missingIfAbsent,
        }
        for item in payload.preparedQuestions[:3]
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
        f"Professor rubric config: {rubric.model_dump_json() if rubric else '{}'}\n"
        f"Project context: {json.dumps({'title': payload.projectContext.title, 'rubric': payload.projectContext.rubric[:6]})}\n"
        f"Current slide: {slide_summary}\n"
        f"Transcript evidence: {json.dumps({'summary': transcript_evidence.summary, 'claims': transcript_evidence.claims[:2], 'technicalChoices': transcript_evidence.technicalChoices[:2], 'metrics': transcript_evidence.metrics[:3], 'unansweredGaps': transcript_evidence.unansweredGaps[:3]})}\n"
        f"Prepared questions: {json.dumps(prepared_questions)}\n"
        f"Recent transcript: {json.dumps(payload.recentTranscript[-2:])}\n"
        f"Recent feedback: {json.dumps(payload.recentFeedback[-2:])}\n"
        f"Latest transcript chunk: {json.dumps(payload.transcriptChunk[:280])}"
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
