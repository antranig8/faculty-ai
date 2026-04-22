from datetime import timedelta
import logging

from fastapi import APIRouter, HTTPException

from app.models.request_models import AnalyzeChunkRequest
from app.models.response_models import AnalyzeChunkResponse
from app.services.answer_resolution import resolve_latest_feedback_if_answered
from app.services.cooldown import _normalize_message, can_emit_feedback, utc_now
from app.services.faculty_brain import decide_faculty_feedback
from app.services.feedback_engine import generate_candidate_feedback, generate_slide_aware_feedback, generate_slide_handoff_feedback
from app.services.llm_errors import classify_llm_error, log_llm_exception
from app.services.llm_feedback import generate_llm_feedback
from app.services.slide_inference import infer_current_slide
import app.state as state

router = APIRouter(tags=["analysis"])
logger = logging.getLogger("faculty_ai.analysis")
LIVE_LLM_MIN_GAP_SECONDS = 20
LIVE_LLM_BACKOFF_SECONDS = 90


def _normalize_chunk(text: str) -> str:
    return " ".join(text.lower().split())


def _llm_backoff_active(session: dict) -> bool:
    backoff_until = session.get("llm_backoff_until")
    return bool(backoff_until and utc_now() < backoff_until)


def _can_attempt_live_llm(session: dict) -> bool:
    if _llm_backoff_active(session):
        return False
    last_attempt_at = session.get("last_llm_attempt_at")
    if not last_attempt_at:
        return True
    return (utc_now() - last_attempt_at).total_seconds() >= LIVE_LLM_MIN_GAP_SECONDS


def _mark_live_llm_attempt(session: dict) -> None:
    session["last_llm_attempt_at"] = utc_now()


def _mark_live_llm_backoff(session: dict) -> None:
    session["llm_backoff_until"] = utc_now() + timedelta(seconds=LIVE_LLM_BACKOFF_SECONDS)


@router.post("/analyze-chunk", response_model=AnalyzeChunkResponse)
def analyze_chunk(payload: AnalyzeChunkRequest) -> AnalyzeChunkResponse:
    session = state.get_session(payload.sessionId)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    normalized_chunk = _normalize_chunk(payload.transcriptChunk)
    if not normalized_chunk:
        return AnalyzeChunkResponse(trigger=False, reason="Transcript chunk is empty.")

    if session.get("last_transcript_chunk") == normalized_chunk:
        return AnalyzeChunkResponse(trigger=False, reason="Duplicate transcript chunk ignored.")

    session["last_transcript_chunk"] = normalized_chunk
    session["transcript"].append(payload.transcriptChunk)
    state.save_session(payload.sessionId, session)
    inferred_slide = infer_current_slide(
        " ".join([*payload.recentTranscript[-4:], payload.transcriptChunk]),
        payload.presentationSlides,
        payload.currentSlide.slideNumber if payload.currentSlide else None,
    )
    effective_slide = inferred_slide or payload.currentSlide
    current_slide_number = effective_slide.slideNumber if effective_slide else None
    recent_feedback_messages = [item.message for item in session.get("feedback", [])][-5:]
    asked_messages = list(session.get("asked_feedback_messages", []))
    resolved_feedback = resolve_latest_feedback_if_answered(
        feedback_items=session.get("feedback", []),
        transcript_chunk=payload.transcriptChunk,
        recent_transcript=payload.recentTranscript,
        prepared_questions=payload.preparedQuestions,
    )
    if resolved_feedback:
        session["awaiting_answer_until"] = None
        state.save_session(payload.sessionId, session)
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason=resolved_feedback.resolutionReason,
            inferredCurrentSlide=inferred_slide,
        )

    candidate, reason = generate_slide_handoff_feedback(
        payload.transcriptChunk,
        recent_transcript=payload.recentTranscript,
        prepared_questions=payload.preparedQuestions,
        current_slide_number=current_slide_number,
        asked_question_ids=list(session.get("asked_feedback_question_ids", [])),
    )

    if candidate is None:
        candidate, reason = generate_slide_aware_feedback(
            payload.transcriptChunk,
            recent_transcript=payload.recentTranscript,
            prepared_questions=payload.preparedQuestions,
            current_slide_number=current_slide_number,
        )

    if candidate is None and _can_attempt_live_llm(session):
        _mark_live_llm_attempt(session)
        state.save_session(payload.sessionId, session)
        try:
            faculty_brain = decide_faculty_feedback(
                payload=payload,
                current_slide=effective_slide,
                recent_feedback=recent_feedback_messages,
                asked_messages=asked_messages,
            )
        except Exception as exc:
            log_llm_exception("decide_faculty_feedback", exc)
            if "rate limit" in classify_llm_error(exc).lower() or "429" in classify_llm_error(exc):
                _mark_live_llm_backoff(session)
                state.save_session(payload.sessionId, session)
            faculty_brain = None

        if faculty_brain and faculty_brain.terminal:
            if faculty_brain.feedback is None:
                return AnalyzeChunkResponse(
                    trigger=False,
                    resolvedFeedback=resolved_feedback,
                    reason=faculty_brain.reason,
                    inferredCurrentSlide=inferred_slide,
                )
            candidate, reason = faculty_brain.feedback, faculty_brain.reason
        elif candidate is None and not payload.preparedQuestions:
            llm_result = None
            try:
                llm_result = generate_llm_feedback(payload)
            except Exception as exc:
                log_llm_exception("generate_llm_feedback", exc)
                classified = classify_llm_error(exc)
                if "rate limit" in classified.lower() or "429" in classified:
                    _mark_live_llm_backoff(session)
                    state.save_session(payload.sessionId, session)
                reason = f"LLM fallback failed: {classified}"

            if llm_result is not None:
                candidate, reason = llm_result

    elif candidate is None and _llm_backoff_active(session):
        reason = "LLM backoff active after provider rate limit. Using deterministic faculty logic only."

    if candidate is None:
        candidate, reason = generate_candidate_feedback(payload.transcriptChunk, project_title=payload.projectContext.title)

    if candidate is None:
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason=reason,
            inferredCurrentSlide=inferred_slide,
        )

    # Let the presenter establish context before lower-priority interruptions fire.
    if len(session["transcript"]) < 2 and candidate.priority == "low":
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason="Warm-up window: waiting for more live context before interrupting.",
            inferredCurrentSlide=inferred_slide,
        )

    awaiting_answer_until = session.get("awaiting_answer_until")
    if awaiting_answer_until and utc_now() < awaiting_answer_until:
        if session.get("last_feedback_slide_number") == current_slide_number:
            return AnalyzeChunkResponse(
                trigger=False,
                resolvedFeedback=resolved_feedback,
                reason="Answer window active: waiting for the presenter to respond before asking another question.",
                inferredCurrentSlide=inferred_slide,
            )

    normalized_message = _normalize_message(candidate.message)
    if normalized_message in session.get("asked_feedback_messages", []):
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason="This faculty question was already asked earlier in the session.",
            inferredCurrentSlide=inferred_slide,
        )

    if candidate.sourceQuestionId and candidate.sourceQuestionId in session.get("asked_feedback_question_ids", []):
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason="This prepared faculty concern was already asked earlier in the session.",
            inferredCurrentSlide=inferred_slide,
        )

    if any(_normalize_message(item.message) == normalized_message for item in session.get("feedback", [])):
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason="This faculty question is already in the feedback history.",
            inferredCurrentSlide=inferred_slide,
        )

    if candidate.sourceQuestionId and any(
        item.sourceQuestionId == candidate.sourceQuestionId for item in session.get("feedback", [])
    ):
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason="This prepared faculty concern is already in the feedback history.",
            inferredCurrentSlide=inferred_slide,
        )

    if current_slide_number is not None and current_slide_number in session.get("asked_feedback_slide_numbers", []):
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason="This slide already received its one faculty question for this presentation.",
            inferredCurrentSlide=inferred_slide,
        )

    allowed, filter_reason = can_emit_feedback(session, candidate.message)
    if not allowed:
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason=filter_reason,
            inferredCurrentSlide=inferred_slide,
        )

    session["feedback"].append(candidate)
    session["last_feedback_at"] = utc_now()
    session.setdefault("asked_feedback_messages", []).append(normalized_message)
    if candidate.sourceQuestionId:
        session.setdefault("asked_feedback_question_ids", []).append(candidate.sourceQuestionId)
    if current_slide_number is not None:
        session.setdefault("asked_feedback_slide_numbers", []).append(current_slide_number)
    session["awaiting_answer_until"] = utc_now() + timedelta(seconds=15)
    session["last_feedback_slide_number"] = current_slide_number
    state.save_session(payload.sessionId, session)
    logger.info(
        "triggered feedback session=%s slide=%s source=%s reason=%s",
        payload.sessionId[:8],
        current_slide_number,
        candidate.sourceQuestionId or "heuristic",
        reason,
    )
    return AnalyzeChunkResponse(
        trigger=True,
        feedback=candidate,
        resolvedFeedback=resolved_feedback,
        reason=reason,
        inferredCurrentSlide=inferred_slide,
    )
