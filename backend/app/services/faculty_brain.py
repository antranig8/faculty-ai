import json
from dataclasses import dataclass
from datetime import timezone

from pydantic import ValidationError

from app.config import get_settings
from app.models.request_models import AnalyzeChunkRequest
from app.models.response_models import FeedbackItem, PreparedQuestion, Slide
from app.services.cooldown import _normalize_message, utc_now
from app.services.groq_client import build_groq_client, groq_reasoning_effort
from app.services.prompt_loader import load_prompt
from app.services.rubric_loader import load_professor_config_from_template
from app.services.section_tracker import infer_section
from app.services.transcript_evidence import TranscriptEvidence, extract_transcript_evidence

_FALLBACK_PROMPT = (
    "You are FacultyAI's runtime faculty-brain.\n"
    "Choose from the prepared slide concerns when deciding whether to interrupt.\n"
    "Use the live transcript to decide timing, not to invent a different question.\n"
    "Return strict JSON only."
)
LIVE_FACULTY_MAX_COMPLETION_TOKENS = 170
MAX_TEXT_CHARS = 220


@dataclass
class FacultyBrainDecision:
    feedback: FeedbackItem | None
    reason: str
    terminal: bool


def _created_at() -> str:
    return utc_now().astimezone(timezone.utc).isoformat()


def _load_prompt() -> str:
    return load_prompt("faculty_brain_runtime.md", _FALLBACK_PROMPT)


def _priority_rank(priority: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(priority, 0)


def _clip_text(value: str, limit: int = MAX_TEXT_CHARS) -> str:
    compacted = " ".join(value.split())
    return compacted if len(compacted) <= limit else f"{compacted[:limit].rstrip()}..."


def _clip_list(items: list[str], count: int = 3, char_limit: int = 80) -> list[str]:
    return [_clip_text(item, char_limit) for item in items if item][:count]


def _build_feedback_from_question(
    payload: AnalyzeChunkRequest,
    question: PreparedQuestion,
    reason: str,
    evidence_heard: list[str] | None = None,
    evidence_missing: list[str] | None = None,
) -> FeedbackItem:
    section = infer_section(" ".join([*payload.recentTranscript[-5:], payload.transcriptChunk]))
    heard = [item for item in (evidence_heard or []) if item][:3]
    missing = [item for item in (evidence_missing or []) if item][:3]
    evidence_summary = ""
    if heard or missing:
        evidence_summary = f" Heard: {', '.join(heard) or 'none'}. Missing: {', '.join(missing) or 'none'}."

    return FeedbackItem(
        type=question.type,
        priority=question.priority,
        section=section,
        message=question.question,
        reason=f"Rubric focus: {question.rubricCategory}. {reason}{evidence_summary}".strip(),
        createdAt=_created_at(),
        sourceQuestionId=question.id,
        autoResolutionTerms=question.missingIfAbsent[:8],
    )


def _build_candidate_payload(question: PreparedQuestion, recent_text: str, asked_messages: list[str], evidence: TranscriptEvidence) -> dict:
    lower_recent = recent_text.lower()
    heard_terms = [term for term in question.listenFor if term.lower() in lower_recent][:6]
    heard_terms.extend([item for item in evidence.evidenceMarkers if item not in heard_terms][:2])
    still_missing = [term for term in question.missingIfAbsent if term.lower() not in lower_recent][:6]
    if evidence.unansweredGaps:
        still_missing.extend([item for item in evidence.unansweredGaps if item not in still_missing][:2])
    already_covered = [term for term in question.missingIfAbsent if term.lower() in lower_recent][:6]
    match_score = (_priority_rank(question.priority) * 2) + (len(heard_terms) * 3) - len(already_covered)

    return {
        "id": question.id,
        "slideNumber": question.slideNumber,
        "rubricCategory": question.rubricCategory,
        "type": question.type,
        "priority": question.priority,
        "question": _clip_text(question.question, 160),
        "listenFor": _clip_list(question.listenFor, 5, 40),
        "missingIfAbsent": _clip_list(question.missingIfAbsent, 5, 50),
        "heardTerms": _clip_list(heard_terms, 5, 40),
        "stillMissing": _clip_list(still_missing, 5, 50),
        "alreadyCovered": _clip_list(already_covered, 4, 50),
        "alreadyAsked": _normalize_message(question.question) in asked_messages,
        "matchScore": match_score,
    }


def _select_confident_candidate(
    payload: AnalyzeChunkRequest,
    prepared_questions: list[PreparedQuestion],
    asked_messages: list[str],
    evidence: TranscriptEvidence,
) -> tuple[PreparedQuestion, list[str], list[str]] | None:
    if len(payload.recentTranscript) + 1 < 3:
        return None

    recent_text = " ".join([*payload.recentTranscript[-5:], payload.transcriptChunk]).lower()
    ranked: list[tuple[int, PreparedQuestion, list[str], list[str]]] = []
    for question in prepared_questions:
        normalized_question = _normalize_message(question.question)
        if normalized_question in asked_messages:
            continue

        heard_terms = [term for term in question.listenFor if term.lower() in recent_text]
        heard_terms.extend([item for item in evidence.evidenceMarkers if item not in heard_terms][:2])
        still_missing = [term for term in question.missingIfAbsent if term.lower() not in recent_text]
        still_missing.extend([item for item in evidence.unansweredGaps if item not in still_missing][:2])
        already_covered = [term for term in question.missingIfAbsent if term.lower() in recent_text]
        if len(heard_terms) < (1 if question.priority == "high" else 2):
            continue
        if not still_missing:
            continue

        score = (_priority_rank(question.priority) * 3) + (len(heard_terms) * 3) + len(still_missing) - (len(already_covered) * 2)
        ranked.append((score, question, heard_terms[:3], still_missing[:3]))

    if not ranked:
        return None

    ranked.sort(key=lambda item: item[0], reverse=True)
    best_score, best_question, heard_terms, missing_terms = ranked[0]
    threshold = 9 if best_question.priority == "high" else 11
    if best_score < threshold:
        return None
    return best_question, heard_terms, missing_terms


def _build_messages(
    payload: AnalyzeChunkRequest,
    current_slide: Slide,
    prepared_questions: list[PreparedQuestion],
    recent_feedback: list[str],
    asked_messages: list[str],
) -> list[dict[str, str]]:
    rubric = load_professor_config_from_template()
    recent_text = " ".join([*payload.recentTranscript[-3:], payload.transcriptChunk]).strip()
    transcript_evidence = extract_transcript_evidence(payload.recentTranscript, payload.transcriptChunk)
    candidate_payload = [
        _build_candidate_payload(question, recent_text, asked_messages, transcript_evidence)
        for question in prepared_questions
    ]
    candidate_payload.sort(key=lambda item: item["matchScore"], reverse=True)
    top_candidates = candidate_payload[:2]

    runtime_context = {
        "courseName": rubric.courseName if rubric else "ENES 104",
        "assignmentName": rubric.assignmentName if rubric else "Project Presentation",
        "questionStyle": rubric.questionStyle if rubric else "skeptical but fair faculty examiner",
        "rubricCriteria": (rubric.rubric if rubric else payload.projectContext.rubric)[:6],
        "assignmentContext": _clip_text(rubric.assignmentContext if rubric else payload.projectContext.notes or "", 160),
        "projectContext": {
            "title": _clip_text(payload.projectContext.title, 120),
            "rubric": payload.projectContext.rubric[:6],
        },
        "currentSlide": {
            "slideNumber": current_slide.slideNumber,
            "title": _clip_text(current_slide.title, 120),
        },
        "transcriptEvidence": {
            "summary": _clip_text(transcript_evidence.summary, 180),
            "claims": _clip_list(transcript_evidence.claims, 2, 120),
            "technicalChoices": _clip_list(transcript_evidence.technicalChoices, 2, 120),
            "metrics": transcript_evidence.metrics[:3],
            "evidenceMarkers": transcript_evidence.evidenceMarkers[:3],
            "tradeoffMarkers": transcript_evidence.tradeoffMarkers[:3],
            "unansweredGaps": _clip_list(transcript_evidence.unansweredGaps, 3, 120),
        },
        "candidateQuestions": top_candidates,
        "recentTranscript": _clip_list(payload.recentTranscript[-2:], 2, 180),
        "latestTranscriptChunk": _clip_text(payload.transcriptChunk, 220),
        "recentFeedback": _clip_list(recent_feedback[-1:], 1, 120),
        "transcriptChunkCount": len(payload.recentTranscript) + 1,
    }

    user_prompt = (
        'Choose ask_now, wait, or skip. Use only candidateQuestions ids. Prefer wait if uncertain.\n'
        f"Runtime context: {json.dumps(runtime_context)}"
    )

    return [
        {"role": "system", "content": _load_prompt()},
        {"role": "user", "content": user_prompt},
    ]


def _parse_json_object(raw_content: str) -> dict:
    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError("Faculty brain response was not valid JSON.")

    try:
        parsed = json.loads(raw_content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("Unable to parse faculty brain JSON response.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Faculty brain response was not a JSON object.")

    return parsed


def decide_faculty_feedback(
    payload: AnalyzeChunkRequest,
    current_slide: Slide | None,
    recent_feedback: list[str],
    asked_messages: list[str],
) -> FacultyBrainDecision:
    if current_slide is None:
        return FacultyBrainDecision(feedback=None, reason="No active slide available for faculty-brain reasoning.", terminal=False)

    prepared_for_slide = [
        question for question in payload.preparedQuestions if question.slideNumber == current_slide.slideNumber
    ]
    if not prepared_for_slide:
        return FacultyBrainDecision(
            feedback=None,
            reason="No prepared slide concerns exist for the active slide.",
            terminal=False,
        )

    settings = get_settings()
    if settings.faculty_ai_llm_provider not in {"groq", "openai"} or not settings.groq_api_key:
        return FacultyBrainDecision(
            feedback=None,
            reason="Faculty-brain LLM is unavailable, falling back to deterministic reasoning.",
            terminal=False,
        )

    transcript_evidence = extract_transcript_evidence(payload.recentTranscript, payload.transcriptChunk)
    confident_candidate = _select_confident_candidate(payload, prepared_for_slide, asked_messages, transcript_evidence)
    if confident_candidate is not None:
        question, heard_terms, missing_terms = confident_candidate
        feedback = _build_feedback_from_question(
            payload=payload,
            question=question,
            reason="Prepared slide concern matched live transcript evidence without needing LLM arbitration.",
            evidence_heard=heard_terms,
            evidence_missing=missing_terms,
        )
        return FacultyBrainDecision(feedback=feedback, reason=feedback.reason, terminal=True)

    client = build_groq_client(settings.groq_api_key)
    completion = client.chat.completions.create(
        model=settings.faculty_ai_llm_model,
        messages=_build_messages(
            payload=payload,
            current_slide=current_slide,
            prepared_questions=prepared_for_slide,
            recent_feedback=recent_feedback,
            asked_messages=asked_messages,
        ),
        temperature=0.1,
        max_completion_tokens=LIVE_FACULTY_MAX_COMPLETION_TOKENS,
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
        return FacultyBrainDecision(feedback=None, reason="Faculty brain returned no content.", terminal=False)

    parsed = _parse_json_object(raw_content)
    decision = str(parsed.get("decision", "skip")).strip().lower()
    reason = str(parsed.get("reason", "")).strip() or "Faculty brain declined to interrupt."
    if decision == "wait":
        confident_candidate = _select_confident_candidate(payload, prepared_for_slide, asked_messages, transcript_evidence)
        if confident_candidate is not None:
            question, heard_terms, missing_terms = confident_candidate
            feedback = _build_feedback_from_question(
                payload=payload,
                question=question,
                reason="Prepared slide concern became timely during the live explanation.",
                evidence_heard=heard_terms,
                evidence_missing=missing_terms,
            )
            return FacultyBrainDecision(feedback=feedback, reason=reason, terminal=True)
        return FacultyBrainDecision(feedback=None, reason=reason, terminal=False)

    if decision == "skip":
        return FacultyBrainDecision(feedback=None, reason=reason, terminal=True)

    if decision != "ask_now":
        raise RuntimeError("Faculty brain returned an unsupported decision.")

    selected_id = str(parsed.get("selectedQuestionId", "")).strip()
    if not selected_id:
        raise RuntimeError("Faculty brain returned ask_now without a selected question id.")

    selected_question = next((item for item in prepared_for_slide if item.id == selected_id), None)
    if selected_question is None:
        raise RuntimeError("Faculty brain selected an unknown question id.")

    evidence_heard = [str(item).strip() for item in parsed.get("evidenceHeard", []) if str(item).strip()]
    evidence_missing = [str(item).strip() for item in parsed.get("evidenceMissing", []) if str(item).strip()]
    suggested_message = str(parsed.get("suggestedMessage", "")).strip() or selected_question.question

    try:
        feedback = _build_feedback_from_question(
            payload=payload,
            question=selected_question.model_copy(update={"question": suggested_message}),
            reason=reason,
            evidence_heard=evidence_heard,
            evidence_missing=evidence_missing,
        )
    except ValidationError as exc:
        raise RuntimeError("Faculty brain returned feedback in an invalid shape.") from exc

    return FacultyBrainDecision(feedback=feedback, reason=reason, terminal=True)
