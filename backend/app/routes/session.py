from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.models.request_models import SessionStartRequest
from app.models.response_models import FeedbackItem, SessionStartResponse
from app.state import sessions

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/start", response_model=SessionStartResponse)
def start_session(payload: SessionStartRequest) -> SessionStartResponse:
    session_id = uuid4().hex
    sessions[session_id] = {
        "project_context": payload.projectContext,
        "transcript": [],
        "feedback": [],
        "last_feedback_at": None,
    }
    return SessionStartResponse(sessionId=session_id)


@router.get("/{session_id}/feedback", response_model=list[FeedbackItem])
def get_feedback(session_id: str) -> list[FeedbackItem]:
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session["feedback"]

