from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from app.models.request_models import ProjectContext
from app.models.response_models import FeedbackItem, PresentationPrepareResponse, ProfessorConfig, Slide

_DB_PATH = Path(__file__).resolve().parents[2] / "faculty_ai.db"

sessions: dict[str, dict[str, Any]] = {}
professor_config = ProfessorConfig()
prepared_question_cache: dict[str, PresentationPrepareResponse] = {}


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
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
    return json.dumps(
        {
            "project_context": session["project_context"].model_dump(mode="json"),
            "transcript": session["transcript"],
            "feedback": [item.model_dump(mode="json") for item in session["feedback"]],
            "last_feedback_at": session["last_feedback_at"].isoformat() if session["last_feedback_at"] else None,
            "last_transcript_chunk": session.get("last_transcript_chunk"),
            "asked_feedback_messages": list(session.get("asked_feedback_messages", [])),
        }
    )


def _deserialize_session(payload: str) -> dict[str, Any]:
    raw = json.loads(payload)
    return {
        "project_context": ProjectContext(**raw["project_context"]),
        "transcript": list(raw.get("transcript", [])),
        "feedback": [FeedbackItem(**item) for item in raw.get("feedback", [])],
        "last_feedback_at": datetime.fromisoformat(raw["last_feedback_at"]) if raw.get("last_feedback_at") else None,
        "last_transcript_chunk": raw.get("last_transcript_chunk"),
        "asked_feedback_messages": list(raw.get("asked_feedback_messages", [])),
    }


def _serialize_preparation(response: PresentationPrepareResponse) -> str:
    return response.model_dump_json()


def _deserialize_preparation(payload: str) -> PresentationPrepareResponse:
    return PresentationPrepareResponse.model_validate_json(payload)


def load_persisted_state() -> None:
    global professor_config
    _init_db()

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
    payload = {
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
