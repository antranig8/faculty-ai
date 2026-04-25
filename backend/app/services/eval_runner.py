import argparse
import json
import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import app.state as state
from app.models.request_models import AnalyzeChunkRequest
from app.models.response_models import Slide
from app.routes.analyze import analyze_chunk
from app.services.feedback_engine import diagnose_hybrid_candidates
from app.services.pptx_parser import parse_pptx_slides
from app.services.presentation_preparer import parse_slide_outline, prepare_questions, prepare_questions_with_llm


def _load_scenario(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _project_context_from_scenario(raw: dict):
    provided = raw.get("projectContext")
    if provided:
        from app.models.request_models import ProjectContext
        return ProjectContext(**provided)
    return state.professor_config_to_project_context()


def _slides_from_scenario(base_dir: Path, raw: dict) -> list[Slide]:
    pptx_path = raw.get("pptxPath")
    if pptx_path:
        resolved = (base_dir / pptx_path).resolve()
        return parse_pptx_slides(resolved.read_bytes())

    slide_outline = raw.get("slideOutline", "")
    return parse_slide_outline(slide_outline)


def _prepare_questions(project_context, slides):
    llm_questions = None
    try:
        llm_questions = prepare_questions_with_llm(project_context, slides)
    except Exception:
        llm_questions = None

    if llm_questions is None:
        return prepare_questions(project_context, slides), "heuristic"

    covered = {item.slideNumber for item in llm_questions}
    fallback = [
        item
        for item in prepare_questions(project_context, slides)
        if item.slideNumber not in covered
    ]
    return [*llm_questions, *fallback], "llm"


def _build_session(project_context) -> dict:
    return {
        "project_context": project_context,
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


def _find_slide(slides: list[Slide], slide_number: int | None) -> Slide | None:
    if slide_number is None:
        return None
    return next((slide for slide in slides if slide.slideNumber == slide_number), None)


def _advance_session_clock(session_id: str, seconds: float) -> None:
    if seconds <= 0:
        return

    session = state.get_session(session_id)
    if not session:
        return

    delta = timedelta(seconds=seconds)
    for key in ["last_feedback_at", "awaiting_answer_until", "last_llm_attempt_at", "llm_backoff_until", "last_transcript_at"]:
        value = session.get(key)
        if value is not None:
            session[key] = value - delta

    state.save_session(session_id, session)


def run_scenario(scenario_path: Path, output_path: Path | None = None) -> dict:
    raw = _load_scenario(scenario_path)
    base_dir = scenario_path.parent
    project_context = _project_context_from_scenario(raw)
    slides = _slides_from_scenario(base_dir, raw)
    prepared_questions, question_source = _prepare_questions(project_context, slides)
    chunks: list[str] = raw.get("transcriptChunks", [])
    slide_sequence: list[int] = raw.get("slideSequence", [])
    slide_mode = raw.get("slideMode", "manual" if slide_sequence else "auto")
    chunk_durations: list[float] = raw.get("chunkDurationsSeconds", [])
    default_chunk_duration = float(raw.get("defaultChunkDurationSeconds", 4.0))

    session_id = f"eval-{uuid4().hex}"
    state.save_session(session_id, _build_session(project_context))

    transcript: list[str] = []
    current_slide = _find_slide(slides, slide_sequence[0]) if slide_sequence else (slides[0] if slides else None)
    report_rows: list[dict] = []
    faculty_ai_notes = raw.get("facultyAINotes", [])
    force_heuristic_runtime = bool(raw.get("forceHeuristicRuntime", True))
    previous_llm_provider = os.environ.get("FACULTY_AI_LLM_PROVIDER")
    elapsed_on_slide = 0.0
    previous_replay_slide_number = current_slide.slideNumber if current_slide else None

    try:
        if force_heuristic_runtime:
            # Keep eval replays deterministic unless a scenario explicitly opts
            # into the live LLM arbitration path for comparison.
            os.environ["FACULTY_AI_LLM_PROVIDER"] = "heuristic"

        for index, chunk in enumerate(chunks):
            if index > 0:
                prior_duration = float(chunk_durations[index - 1]) if (index - 1) < len(chunk_durations) else default_chunk_duration
                _advance_session_clock(session_id, prior_duration)

            if slide_sequence and index < len(slide_sequence):
                current_slide = _find_slide(slides, slide_sequence[index]) or current_slide
            current_slide_number = current_slide.slideNumber if current_slide else None
            if current_slide_number != previous_replay_slide_number:
                elapsed_on_slide = 0.0
            elapsed_on_slide += float(chunk_durations[index]) if index < len(chunk_durations) else default_chunk_duration
            previous_replay_slide_number = current_slide_number

            diagnostics = diagnose_hybrid_candidates(
                text=chunk,
                recent_transcript=transcript[-4:],
                prepared_questions=prepared_questions,
                current_slide=current_slide,
                project_title=project_context.title,
                student_profiles=state.get_session(session_id).get("student_profiles", {}),
            )

            payload = AnalyzeChunkRequest(
                sessionId=session_id,
                transcriptChunk=chunk,
                recentTranscript=transcript[-4:],
                recentFeedback=[],
                projectContext=project_context,
                currentSlide=current_slide,
                slideMode=slide_mode,
                presentationSlides=slides,
                preparedQuestions=prepared_questions,
                studentCoverage=state.get_session(session_id).get("student_coverage", {}),
                studentProfiles=state.get_session(session_id).get("student_profiles", {}),
                simulatedSecondsOnSlide=elapsed_on_slide,
            )
            result = analyze_chunk(payload)

            transcript.append(chunk)
            if slide_mode == "auto" and result.inferredCurrentSlide is not None:
                current_slide = result.inferredCurrentSlide

            report_rows.append(
                {
                    "index": index,
                    "chunk": chunk,
                    "currentSlideNumber": current_slide.slideNumber if current_slide else None,
                    "decision": "trigger" if result.trigger else "no_trigger",
                    "feedback": result.feedback.model_dump(mode="json") if result.feedback else None,
                    "queuedFeedback": result.queuedFeedback.model_dump(mode="json") if result.queuedFeedback else None,
                    "resolvedFeedback": result.resolvedFeedback.model_dump(mode="json") if result.resolvedFeedback else None,
                    "answerEvaluation": result.answerEvaluation.model_dump(mode="json") if result.answerEvaluation else None,
                    "reason": result.reason,
                    "diagnostics": diagnostics,
                }
            )
    finally:
        if force_heuristic_runtime:
            if previous_llm_provider is None:
                os.environ.pop("FACULTY_AI_LLM_PROVIDER", None)
            else:
                os.environ["FACULTY_AI_LLM_PROVIDER"] = previous_llm_provider
        state.delete_session(session_id)

    report = {
        "scenario": str(scenario_path),
        "questionSource": question_source,
        "runtimeMode": "heuristic" if force_heuristic_runtime else "configured",
        "slideCount": len(slides),
        "preparedQuestionCount": len(prepared_questions),
        "facultyAINotes": faculty_ai_notes,
        "rows": report_rows,
    }

    if output_path:
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a saved FacultyAI scenario and print selection diagnostics.")
    parser.add_argument("scenario", help="Path to a scenario JSON file.")
    parser.add_argument("--out", help="Optional path to write the JSON report.")
    args = parser.parse_args()

    scenario_path = Path(args.scenario).resolve()
    output_path = Path(args.out).resolve() if args.out else None
    report = run_scenario(scenario_path, output_path=output_path)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
