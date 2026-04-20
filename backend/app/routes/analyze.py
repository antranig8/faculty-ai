from fastapi import APIRouter, HTTPException

from app.models.request_models import AnalyzeChunkRequest
from app.models.response_models import AnalyzeChunkResponse
from app.services.cooldown import can_emit_feedback, utc_now
from app.services.feedback_engine import generate_candidate_feedback, generate_slide_aware_feedback
from app.state import sessions

router = APIRouter(tags=["analysis"])


@router.post("/analyze-chunk", response_model=AnalyzeChunkResponse)
def analyze_chunk(payload: AnalyzeChunkRequest) -> AnalyzeChunkResponse:
    session = sessions.get(payload.sessionId)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session["transcript"].append(payload.transcriptChunk)
    current_slide_number = payload.currentSlide.slideNumber if payload.currentSlide else None
    candidate, reason = generate_slide_aware_feedback(
        payload.transcriptChunk,
        recent_transcript=payload.recentTranscript,
        prepared_questions=payload.preparedQuestions,
        current_slide_number=current_slide_number,
    )

    if candidate is None:
        candidate, reason = generate_candidate_feedback(
            payload.transcriptChunk,
            project_title=payload.projectContext.title,
        )

    if candidate is None:
        return AnalyzeChunkResponse(trigger=False, reason=reason)

    allowed, filter_reason = can_emit_feedback(session, candidate.message)
    if not allowed:
        return AnalyzeChunkResponse(trigger=False, reason=filter_reason)

    session["feedback"].append(candidate)
    session["last_feedback_at"] = utc_now()
    return AnalyzeChunkResponse(trigger=True, feedback=candidate, reason=reason)
