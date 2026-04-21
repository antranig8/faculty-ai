from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.models.request_models import SessionStartRequest
from app.models.response_models import FeedbackItem, FinalEvaluation, SessionStartResponse
from app.services.final_evaluator import evaluate_presentation
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
        "awaiting_answer_until": None,
        "last_feedback_slide_number": None,
        "last_llm_attempt_at": None,
        "llm_backoff_until": None,
    }
    state.save_session(session_id, session)
    return SessionStartResponse(sessionId=session_id)


@router.get("/{session_id}/feedback", response_model=list[FeedbackItem])
def get_feedback(session_id: str) -> list[FeedbackItem]:
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session["feedback"]


@router.post("/{session_id}/finalize", response_model=FinalEvaluation)
def finalize_session(session_id: str) -> FinalEvaluation:
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = evaluate_presentation(
        session_id=session_id,
        project_title=session["project_context"].title or "Project Presentation",
        transcript=session["transcript"],
        feedback=session["feedback"],
    )
    state.save_presentation_result(result)
    return result


@router.get("/results", response_model=list[FinalEvaluation])
def get_results() -> list[FinalEvaluation]:
    return state.list_presentation_results()

