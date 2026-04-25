from datetime import timedelta
import logging

from fastapi import APIRouter, HTTPException

from app.models.request_models import AnalyzeChunkRequest
from app.models.response_models import AnalyzeChunkResponse
from app.services.answer_resolution import resolve_latest_feedback_if_answered
from app.services.cooldown import _normalize_message, can_emit_feedback, utc_now
from app.services.faculty_brain import decide_faculty_feedback
from app.services.feedback_engine import (
    generate_candidate_feedback,
    generate_slide_aware_feedback,
    generate_slide_handoff_feedback,
    is_slide_handoff,
)
from app.services.llm_errors import classify_llm_error, log_llm_exception
from app.services.llm_feedback import generate_llm_feedback
from app.services.slide_inference import infer_current_slide
import app.state as state

router = APIRouter(tags=["analysis"])
logger = logging.getLogger("faculty_ai.analysis")
LIVE_LLM_MIN_GAP_SECONDS = 20
LIVE_LLM_BACKOFF_SECONDS = 90
NEW_SLIDE_WARMUP_CHUNKS = 3


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


def _find_slide(slides, slide_number: int | None):
    if slide_number is None:
        return None
    return next((slide for slide in slides if slide.slideNumber == slide_number), None)


def _slide_already_has_feedback(session: dict, slide_number: int | None) -> bool:
    if slide_number is None:
        return False
    return any(item.slideNumber == slide_number for item in session.get("feedback", []))


def _feedback_topic_key(item) -> str | None:
    source = (getattr(item, "sourceQuestionId", None) or "").lower()
    message = _normalize_message(getattr(item, "message", ""))

    if "team-perspective" in source:
        return "takeaways-team-perspective"
    if "individual-application" in source:
        return "individual-application"
    if "course-cip" in source:
        return "course-improvement"
    if "team-feedback" in source:
        return "team-feedback"
    if "architecture" in source:
        return "architecture"
    if "evaluation" in source:
        return "evaluation"
    if "problem-evidence" in source:
        return "problem-evidence"
    if "ai-specificity" in source:
        return "ai-specificity"

    if any(term in message for term in ["most important enes 104 takeaway", "team disagree", "disagreement shape this slide"]):
        return "takeaways-team-perspective"
    if any(term in message for term in ["professionalism", "perseverance", "key takeaways", "lessons to prioritize", "most impactful for future engineers"]):
        return "takeaways-team-perspective"
    if any(term in message for term in ["view of engineering", "specific experience caused", "change next because of that lesson"]):
        return "individual-application"
    if any(term in message for term in ["management could only act on one improvement", "next enes 104 student's experience"]):
        return "course-improvement"
    if any(term in message for term in ["piece of teammate feedback", "changed the final presentation"]):
        return "team-feedback"
    if any(term in message for term in ["architecture", "simpler alternative"]):
        return "architecture"
    if any(term in message for term in ["what metric will show", "metric supports the claim"]):
        return "evaluation"
    if any(term in message for term in ["real problem for the target users", "evidence shows this is a real problem"]):
        return "problem-evidence"
    if any(term in message for term in ["what exactly does the ai decide", "what input does it use"]):
        return "ai-specificity"
    return None


def _topic_already_covered(session: dict, candidate) -> bool:
    candidate_topic = _feedback_topic_key(candidate)
    if not candidate_topic:
        return False
    return any(_feedback_topic_key(item) == candidate_topic for item in session.get("feedback", []))


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
    previous_slide_number = session.get("active_slide_number")
    if payload.slideMode == "manual":
        inferred_slide = payload.currentSlide
        session["candidate_slide_number"] = None
        session["candidate_slide_hits"] = 0
        effective_slide = payload.currentSlide
    elif previous_slide_number is None and payload.currentSlide is not None:
        inferred_slide = payload.currentSlide
        session["candidate_slide_number"] = None
        session["candidate_slide_hits"] = 0
        effective_slide = payload.currentSlide
    else:
        inferred_slide = infer_current_slide(
            " ".join([*payload.recentTranscript[-4:], payload.transcriptChunk]),
            payload.presentationSlides,
            payload.currentSlide.slideNumber if payload.currentSlide else session.get("active_slide_number"),
        )
        if inferred_slide and previous_slide_number and inferred_slide.slideNumber != previous_slide_number:
            if session.get("candidate_slide_number") == inferred_slide.slideNumber:
                session["candidate_slide_hits"] = int(session.get("candidate_slide_hits", 0)) + 1
            else:
                session["candidate_slide_number"] = inferred_slide.slideNumber
                session["candidate_slide_hits"] = 1

            if int(session.get("candidate_slide_hits", 0)) < 2:
                effective_slide = (
                    _find_slide(payload.presentationSlides, previous_slide_number)
                    or payload.currentSlide
                )
                inferred_slide = effective_slide
            else:
                session["candidate_slide_number"] = None
                session["candidate_slide_hits"] = 0
                effective_slide = inferred_slide
        else:
            session["candidate_slide_number"] = None
            session["candidate_slide_hits"] = 0
            effective_slide = inferred_slide or payload.currentSlide

    current_slide_number = effective_slide.slideNumber if effective_slide else None
    slide_changed = current_slide_number is not None and current_slide_number != previous_slide_number
    if current_slide_number is None:
        session["active_slide_number"] = None
        session["active_slide_chunk_count"] = 0
    elif slide_changed:
        session["active_slide_number"] = current_slide_number
        session["active_slide_chunk_count"] = 1
    else:
        session["active_slide_number"] = current_slide_number
        session["active_slide_chunk_count"] = int(session.get("active_slide_chunk_count", 0)) + 1
    slide_chunk_count = int(session.get("active_slide_chunk_count", 0))
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

    if candidate is None and slide_chunk_count >= NEW_SLIDE_WARMUP_CHUNKS:
        candidate, reason = generate_slide_aware_feedback(
            payload.transcriptChunk,
            recent_transcript=payload.recentTranscript,
            prepared_questions=payload.preparedQuestions,
            current_slide_number=current_slide_number,
        )

    if candidate is None and slide_chunk_count >= NEW_SLIDE_WARMUP_CHUNKS and _can_attempt_live_llm(session):
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

    if slide_changed and not is_slide_handoff(payload.transcriptChunk):
        state.save_session(payload.sessionId, session)
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason="Slide warm-up: waiting for more spoken context before interrupting on the new slide.",
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

    if _topic_already_covered(session, candidate):
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason="A faculty question on this same topic was already asked earlier in the session.",
            inferredCurrentSlide=inferred_slide,
        )

    if _slide_already_has_feedback(session, current_slide_number):
        return AnalyzeChunkResponse(
            trigger=False,
            resolvedFeedback=resolved_feedback,
            reason="This slide already received its one faculty question for this presentation.",
            inferredCurrentSlide=inferred_slide,
        )

    # Older sessions may still rely on the side-list. Trim any stale entries once
    # the feedback history says this slide has not actually been asked yet.
    if current_slide_number is not None and current_slide_number in session.get("asked_feedback_slide_numbers", []):
        session["asked_feedback_slide_numbers"] = [
            number
            for number in session.get("asked_feedback_slide_numbers", [])
            if _slide_already_has_feedback(session, number)
        ]

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
