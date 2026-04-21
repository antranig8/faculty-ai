from datetime import timedelta

from fastapi import APIRouter, HTTPException

from app.models.request_models import AnalyzeChunkRequest
from app.models.response_models import AnalyzeChunkResponse
from app.services.cooldown import _normalize_message, can_emit_feedback, utc_now
from app.services.faculty_brain import decide_faculty_feedback
from app.services.feedback_engine import generate_candidate_feedback, generate_slide_aware_feedback
from app.services.llm_feedback import generate_llm_feedback
from app.services.slide_inference import infer_current_slide
import app.state as state

router = APIRouter(tags=["analysis"])


def _normalize_chunk(text: str) -> str:
    return " ".join(text.lower().split())


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
    faculty_brain = decide_faculty_feedback(
        payload=payload,
        current_slide=effective_slide,
        recent_feedback=recent_feedback_messages,
        asked_messages=asked_messages,
    )

    if faculty_brain.terminal:
        if faculty_brain.feedback is None:
            return AnalyzeChunkResponse(trigger=False, reason=faculty_brain.reason, inferredCurrentSlide=inferred_slide)
        candidate, reason = faculty_brain.feedback, faculty_brain.reason
    else:
        candidate, reason = generate_slide_aware_feedback(
            payload.transcriptChunk,
            recent_transcript=payload.recentTranscript,
            prepared_questions=payload.preparedQuestions,
            current_slide_number=current_slide_number,
        )

        if candidate is None:
            llm_result = None
            try:
                llm_result = generate_llm_feedback(payload)
            except RuntimeError as exc:
                reason = f"LLM fallback failed: {exc}"

            if llm_result is not None:
                candidate, reason = llm_result

        if candidate is None:
            candidate, reason = generate_candidate_feedback(payload.transcriptChunk, project_title=payload.projectContext.title)

    if candidate is None:
        return AnalyzeChunkResponse(trigger=False, reason=reason, inferredCurrentSlide=inferred_slide)

    # Let the presenter establish context before low/medium-priority interruptions fire.
    if len(session["transcript"]) < 3 and candidate.priority != "high":
        return AnalyzeChunkResponse(
            trigger=False,
            reason="Warm-up window: waiting for more live context before interrupting.",
            inferredCurrentSlide=inferred_slide,
        )

    awaiting_answer_until = session.get("awaiting_answer_until")
    if awaiting_answer_until and utc_now() < awaiting_answer_until:
        if session.get("last_feedback_slide_number") == current_slide_number:
            return AnalyzeChunkResponse(
                trigger=False,
                reason="Answer window active: waiting for the presenter to respond before asking another question.",
                inferredCurrentSlide=inferred_slide,
            )

    normalized_message = _normalize_message(candidate.message)
    if normalized_message in session.get("asked_feedback_messages", []):
        return AnalyzeChunkResponse(
            trigger=False,
            reason="This faculty question was already asked earlier in the session.",
            inferredCurrentSlide=inferred_slide,
        )

    allowed, filter_reason = can_emit_feedback(session, candidate.message)
    if not allowed:
        return AnalyzeChunkResponse(trigger=False, reason=filter_reason, inferredCurrentSlide=inferred_slide)

    session["feedback"].append(candidate)
    session["last_feedback_at"] = utc_now()
    session.setdefault("asked_feedback_messages", []).append(normalized_message)
    session["awaiting_answer_until"] = utc_now() + timedelta(seconds=40)
    session["last_feedback_slide_number"] = current_slide_number
    state.save_session(payload.sessionId, session)
    return AnalyzeChunkResponse(trigger=True, feedback=candidate, reason=reason, inferredCurrentSlide=inferred_slide)
