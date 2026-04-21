from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.models.request_models import SessionStartRequest
from app.models.response_models import FeedbackItem, SessionStartResponse
import app.state as state

router = APIRouter(prefix="/session", tags=["session"])


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
    }
    state.save_session(session_id, session)
    return SessionStartResponse(sessionId=session_id)


@router.get("/{session_id}/feedback", response_model=list[FeedbackItem])
def get_feedback(session_id: str) -> list[FeedbackItem]:
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session["feedback"]

