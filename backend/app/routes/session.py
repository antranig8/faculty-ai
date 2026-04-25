from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.models.request_models import FeedbackResolutionRequest, SessionStartRequest
from app.models.response_models import FeedbackItem, SessionStartResponse
import app.state as state

router = APIRouter(prefix="/session", tags=["session"])


def _normalize_feedback_message(message: str | None) -> str:
    if not message:
        return ""
    return " ".join(message.lower().split())


@router.post("/start", response_model=SessionStartResponse)
def start_session(payload: SessionStartRequest) -> SessionStartResponse:
    session_id = uuid4().hex
    session = {
        "project_context": payload.projectContext,
        "transcript": [],
        "feedback": [],
        "last_feedback_at": None,
        "last_transcript_chunk": None,
        "asked_feedback_messages": [],
        "asked_feedback_question_ids": [],
        "asked_feedback_slide_numbers": [],
        "awaiting_answer_until": None,
        "last_feedback_slide_number": None,
        "last_llm_attempt_at": None,
        "llm_backoff_until": None,
        "active_slide_number": None,
        "active_slide_chunk_count": 0,
        "candidate_slide_number": None,
        "candidate_slide_hits": 0,
        "queued_feedback": None,
        "follow_up_attempts": {},
        "slide_started_at": None,
        "last_transcript_at": None,
        "student_coverage": {},
        "student_profiles": {},
    }
    state.save_session(session_id, session)
    return SessionStartResponse(sessionId=session_id)


@router.get("/{session_id}/feedback", response_model=list[FeedbackItem])
def get_feedback(session_id: str) -> list[FeedbackItem]:
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session["feedback"]


@router.patch("/{session_id}/feedback/{created_at}/resolution", response_model=list[FeedbackItem])
def update_feedback_resolution(session_id: str, created_at: str, payload: FeedbackResolutionRequest) -> list[FeedbackItem]:
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    feedback = session["feedback"]
    target = next((item for item in feedback if item.createdAt == created_at), None)
    if target is None and payload.sourceQuestionId:
        target = next(
            (
                item for item in reversed(feedback)
                if item.sourceQuestionId == payload.sourceQuestionId
            ),
            None,
        )
    if target is None and payload.message:
        normalized_message = _normalize_feedback_message(payload.message)
        target = next(
            (
                item for item in reversed(feedback)
                if _normalize_feedback_message(item.message) == normalized_message
            ),
            None,
        )

    if target is None:
        raise HTTPException(status_code=404, detail="Feedback item not found")

    target.resolved = payload.resolved
    target.deliveryStatus = "resolved" if payload.resolved else "active"
    target.resolvedAt = state.utc_now_iso() if payload.resolved else None
    target.resolutionReason = payload.resolutionReason if payload.resolved else None

    state.save_session(session_id, session)
    return feedback

