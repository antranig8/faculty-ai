from fastapi import APIRouter, HTTPException

from app.models.request_models import AnalyzeChunkRequest
from app.models.response_models import AnalyzeChunkResponse
from app.services.cooldown import _normalize_message, can_emit_feedback, utc_now
from app.services.feedback_engine import generate_candidate_feedback, generate_slide_aware_feedback
from app.services.llm_feedback import generate_llm_feedback
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
    current_slide_number = payload.currentSlide.slideNumber if payload.currentSlide else None
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
        return AnalyzeChunkResponse(trigger=False, reason=reason)

    # Let the presenter establish context before low/medium-priority interruptions fire.
    if len(session["transcript"]) < 3 and candidate.priority != "high":
        return AnalyzeChunkResponse(trigger=False, reason="Warm-up window: waiting for more live context before interrupting.")

    normalized_message = _normalize_message(candidate.message)
    if normalized_message in session.get("asked_feedback_messages", []):
        return AnalyzeChunkResponse(trigger=False, reason="This faculty question was already asked earlier in the session.")

    allowed, filter_reason = can_emit_feedback(session, candidate.message)
    if not allowed:
        return AnalyzeChunkResponse(trigger=False, reason=filter_reason)

    session["feedback"].append(candidate)
    session["last_feedback_at"] = utc_now()
    session.setdefault("asked_feedback_messages", []).append(normalized_message)
    state.save_session(payload.sessionId, session)
    return AnalyzeChunkResponse(trigger=True, feedback=candidate, reason=reason)
