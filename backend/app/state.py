from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from app.models.request_models import ProjectContext, StudentProfile
from app.models.response_models import FeedbackItem, PresentationPrepareResponse, ProfessorConfig, Slide
from app.services.rubric_loader import load_professor_config_from_template

_DB_PATH = Path(__file__).resolve().parents[2] / "faculty_ai.db"
PREPARED_QUESTION_CACHE_VERSION = "assignment6-reflective-v2"

sessions: dict[str, dict[str, Any]] = {}
professor_config = ProfessorConfig()
prepared_question_cache: dict[str, PresentationPrepareResponse] = {}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    # Keep state in a tiny SQLite schema so the app can survive restarts without
    # introducing a heavier database dependency during local development.
    with _connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
              session_id TEXT PRIMARY KEY,
              payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prepared_question_cache (
              cache_key TEXT PRIMARY KEY,
              payload TEXT NOT NULL
            )
            """
        )


def _persist_value(table: str, key_column: str, key: str, payload: str) -> None:
    with _connection() as conn:
        conn.execute(
            f"INSERT INTO {table} ({key_column}, payload) VALUES (?, ?) "
            f"ON CONFLICT({key_column}) DO UPDATE SET payload = excluded.payload",
            (key, payload),
        )


def _serialize_session(session: dict[str, Any]) -> str:
    # Sessions mix pydantic models with datetime objects, so they need an
    # explicit JSON shape before they can be persisted to SQLite.
    return json.dumps(
        {
            "project_context": session["project_context"].model_dump(mode="json"),
            "transcript": session["transcript"],
            "feedback": [item.model_dump(mode="json") for item in session["feedback"]],
            "last_feedback_at": session["last_feedback_at"].isoformat() if session["last_feedback_at"] else None,
            "last_transcript_chunk": session.get("last_transcript_chunk"),
            "asked_feedback_messages": list(session.get("asked_feedback_messages", [])),
            "asked_feedback_question_ids": list(session.get("asked_feedback_question_ids", [])),
            "asked_feedback_slide_numbers": list(session.get("asked_feedback_slide_numbers", [])),
            "awaiting_answer_until": session["awaiting_answer_until"].isoformat() if session.get("awaiting_answer_until") else None,
            "last_feedback_slide_number": session.get("last_feedback_slide_number"),
            "last_llm_attempt_at": session["last_llm_attempt_at"].isoformat() if session.get("last_llm_attempt_at") else None,
            "llm_backoff_until": session["llm_backoff_until"].isoformat() if session.get("llm_backoff_until") else None,
            "active_slide_number": session.get("active_slide_number"),
            "active_slide_chunk_count": session.get("active_slide_chunk_count", 0),
            "candidate_slide_number": session.get("candidate_slide_number"),
            "candidate_slide_hits": session.get("candidate_slide_hits", 0),
            "queued_feedback": session["queued_feedback"].model_dump(mode="json") if session.get("queued_feedback") else None,
            "follow_up_attempts": dict(session.get("follow_up_attempts", {})),
            "slide_started_at": session["slide_started_at"].isoformat() if session.get("slide_started_at") else None,
            "last_transcript_at": session["last_transcript_at"].isoformat() if session.get("last_transcript_at") else None,
            "student_coverage": dict(session.get("student_coverage", {})),
            "student_profiles": {
                name: profile.model_dump(mode="json")
                for name, profile in session.get("student_profiles", {}).items()
            },
        }
    )


def _deserialize_session(payload: str) -> dict[str, Any]:
    # Rehydrate persisted JSON back into the in-memory session structure the
    # live analysis pipeline expects.
    raw = json.loads(payload)
    return {
        "project_context": ProjectContext(**raw["project_context"]),
        "transcript": list(raw.get("transcript", [])),
        "feedback": [FeedbackItem(**item) for item in raw.get("feedback", [])],
        "last_feedback_at": datetime.fromisoformat(raw["last_feedback_at"]) if raw.get("last_feedback_at") else None,
        "last_transcript_chunk": raw.get("last_transcript_chunk"),
        "asked_feedback_messages": list(raw.get("asked_feedback_messages", [])),
        "asked_feedback_question_ids": list(raw.get("asked_feedback_question_ids", [])),
        "asked_feedback_slide_numbers": list(raw.get("asked_feedback_slide_numbers", [])),
        "awaiting_answer_until": datetime.fromisoformat(raw["awaiting_answer_until"]) if raw.get("awaiting_answer_until") else None,
        "last_feedback_slide_number": raw.get("last_feedback_slide_number"),
        "last_llm_attempt_at": datetime.fromisoformat(raw["last_llm_attempt_at"]) if raw.get("last_llm_attempt_at") else None,
        "llm_backoff_until": datetime.fromisoformat(raw["llm_backoff_until"]) if raw.get("llm_backoff_until") else None,
        "active_slide_number": raw.get("active_slide_number"),
        "active_slide_chunk_count": raw.get("active_slide_chunk_count", 0),
        "candidate_slide_number": raw.get("candidate_slide_number"),
        "candidate_slide_hits": raw.get("candidate_slide_hits", 0),
        "queued_feedback": FeedbackItem(**raw["queued_feedback"]) if raw.get("queued_feedback") else None,
        "follow_up_attempts": dict(raw.get("follow_up_attempts", {})),
        "slide_started_at": datetime.fromisoformat(raw["slide_started_at"]) if raw.get("slide_started_at") else None,
        "last_transcript_at": datetime.fromisoformat(raw["last_transcript_at"]) if raw.get("last_transcript_at") else None,
        "student_coverage": dict(raw.get("student_coverage", {})),
        "student_profiles": {
            name: StudentProfile(**profile)
            for name, profile in raw.get("student_profiles", {}).items()
        },
    }


def _serialize_preparation(response: PresentationPrepareResponse) -> str:
    return response.model_dump_json()


def _deserialize_preparation(payload: str) -> PresentationPrepareResponse:
    return PresentationPrepareResponse.model_validate_json(payload)


def load_persisted_state() -> None:
    global professor_config
    # Startup loads defaults from the prompt-backed rubric template first, then
    # overlays any explicitly saved state from SQLite.
    _init_db()
    template_config = load_professor_config_from_template()
    if template_config:
        professor_config = template_config

    with _connection() as conn:
        config_row = conn.execute("SELECT value FROM app_state WHERE key = 'professor_config'").fetchone()
        if config_row:
            professor_config = ProfessorConfig.model_validate_json(config_row["value"])

        for row in conn.execute("SELECT session_id, payload FROM sessions").fetchall():
            sessions[row["session_id"]] = _deserialize_session(row["payload"])

        for row in conn.execute("SELECT cache_key, payload FROM prepared_question_cache").fetchall():
            prepared_question_cache[row["cache_key"]] = _deserialize_preparation(row["payload"])

def persist_professor_config(config: ProfessorConfig) -> None:
    global professor_config
    professor_config = config
    with _connection() as conn:
        conn.execute(
            "INSERT INTO app_state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("professor_config", config.model_dump_json()),
        )


def build_preparation_cache_key(project_context: ProjectContext, slides: list[Slide]) -> str:
    # Prepared-question generation is expensive enough to cache, so the key is a
    # stable hash over both project context and the extracted slide contents.
    payload = {
        "version": PREPARED_QUESTION_CACHE_VERSION,
        "projectContext": project_context.model_dump(mode="json"),
        "slides": [slide.model_dump(mode="json") for slide in slides],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def save_prepared_question_cache(cache_key: str, response: PresentationPrepareResponse) -> None:
    prepared_question_cache[cache_key] = response
    _persist_value("prepared_question_cache", "cache_key", cache_key, _serialize_preparation(response))


def save_session(session_id: str, session: dict[str, Any]) -> None:
    sessions[session_id] = session
    _persist_value("sessions", "session_id", session_id, _serialize_session(session))


def get_session(session_id: str) -> dict[str, Any] | None:
    session = sessions.get(session_id)
    if session is not None:
        return session

    with _connection() as conn:
        row = conn.execute("SELECT payload FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        return None

    session = _deserialize_session(row["payload"])
    sessions[session_id] = session
    return session


def delete_session(session_id: str) -> None:
    sessions.pop(session_id, None)
    with _connection() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


def professor_config_to_project_context() -> ProjectContext:
    return ProjectContext(
        title=professor_config.assignmentName,
        summary=professor_config.assignmentContext,
        stack=[],
        goals=[],
        rubric=professor_config.rubric,
        notes=professor_config.questionStyle,
    )


load_persisted_state()
