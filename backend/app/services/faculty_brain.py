import json
from dataclasses import dataclass
from datetime import timezone

from groq import Groq
from pydantic import ValidationError

from app.config import get_settings
from app.models.request_models import AnalyzeChunkRequest
from app.models.response_models import FeedbackItem, PreparedQuestion, Slide
from app.services.cooldown import _normalize_message, utc_now
from app.services.prompt_loader import load_prompt
from app.services.rubric_loader import load_professor_config_from_template
from app.services.section_tracker import infer_section

_FALLBACK_PROMPT = (
    "You are FacultyAI's runtime faculty-brain.\n"
    "Choose from the prepared slide concerns when deciding whether to interrupt.\n"
    "Use the live transcript to decide timing, not to invent a different question.\n"
    "Return strict JSON only."
)


@dataclass
class FacultyBrainDecision:
    feedback: FeedbackItem | None
    reason: str
    terminal: bool


def _created_at() -> str:
    return utc_now().astimezone(timezone.utc).isoformat()


def _load_prompt() -> str:
    return load_prompt("faculty_brain_runtime.txt", _FALLBACK_PROMPT)


def _priority_rank(priority: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(priority, 0)


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
    )


def _build_candidate_payload(question: PreparedQuestion, recent_text: str, asked_messages: list[str]) -> dict:
    lower_recent = recent_text.lower()
    heard_terms = [term for term in question.listenFor if term.lower() in lower_recent][:6]
    still_missing = [term for term in question.missingIfAbsent if term.lower() not in lower_recent][:6]
    already_covered = [term for term in question.missingIfAbsent if term.lower() in lower_recent][:6]
    match_score = (_priority_rank(question.priority) * 2) + (len(heard_terms) * 3) - len(already_covered)

    return {
        "id": question.id,
        "slideNumber": question.slideNumber,
        "rubricCategory": question.rubricCategory,
        "type": question.type,
        "priority": question.priority,
        "question": question.question,
        "listenFor": question.listenFor,
        "missingIfAbsent": question.missingIfAbsent,
        "heardTerms": heard_terms,
        "stillMissing": still_missing,
        "alreadyCovered": already_covered,
        "alreadyAsked": _normalize_message(question.question) in asked_messages,
        "matchScore": match_score,
    }


def _select_confident_candidate(
    payload: AnalyzeChunkRequest,
    prepared_questions: list[PreparedQuestion],
    asked_messages: list[str],
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
        still_missing = [term for term in question.missingIfAbsent if term.lower() not in recent_text]
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
    recent_text = " ".join([*payload.recentTranscript[-5:], payload.transcriptChunk]).strip()
    candidate_payload = [
        _build_candidate_payload(question, recent_text, asked_messages)
        for question in prepared_questions
    ]
    candidate_payload.sort(key=lambda item: item["matchScore"], reverse=True)

    runtime_context = {
        "courseName": rubric.courseName if rubric else "ENES 104",
        "assignmentName": rubric.assignmentName if rubric else "Project Presentation",
        "questionStyle": rubric.questionStyle if rubric else "skeptical but fair faculty examiner",
        "rubricCriteria": rubric.rubric if rubric else payload.projectContext.rubric,
        "assignmentContext": rubric.assignmentContext if rubric else payload.projectContext.notes,
        "courseCalibration": (
            "Introduction to engineering professions course. Prepare students for professional industry expectations, "
            "but keep questioning fair and not overly harsh."
        ),
        "projectContext": payload.projectContext.model_dump(),
        "currentSlide": current_slide.model_dump(),
        "candidateQuestions": candidate_payload[:5],
        "recentTranscript": payload.recentTranscript[-5:],
        "latestTranscriptChunk": payload.transcriptChunk,
        "recentFeedback": recent_feedback[-5:],
        "transcriptChunkCount": len(payload.recentTranscript) + 1,
    }

    user_prompt = (
        "Decide whether FacultyAI should ask one prepared faculty question right now.\n"
        "Return strict JSON with this shape:\n"
        '{"decision":"ask_now|wait|skip","reason":string,"selectedQuestionId":string|null,'
        '"evidenceHeard":[string],"evidenceMissing":[string],"suggestedMessage":string|null}\n'
        "Use only the prepared question ids provided in candidateQuestions.\n"
        "Prefer wait over asking too early.\n\n"
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

    client = Groq(api_key=settings.groq_api_key, max_retries=0)
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
        max_completion_tokens=900,
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
        return FacultyBrainDecision(feedback=None, reason="Faculty brain returned no content.", terminal=False)

    parsed = _parse_json_object(raw_content)
    decision = str(parsed.get("decision", "skip")).strip().lower()
    reason = str(parsed.get("reason", "")).strip() or "Faculty brain declined to interrupt."

    if decision == "wait":
        confident_candidate = _select_confident_candidate(payload, prepared_for_slide, asked_messages)
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
