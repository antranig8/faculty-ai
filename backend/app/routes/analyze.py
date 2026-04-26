from datetime import timedelta
import logging

from fastapi import APIRouter, HTTPException

import app.state as state
from app.models.request_models import AnalyzeChunkRequest
from app.models.response_models import AnalyzeChunkResponse, FeedbackItem
from app.services.answer_resolution import evaluate_latest_feedback_answer
from app.services.cooldown import _normalize_message, can_emit_feedback, utc_now
from app.services.faculty_brain import decide_faculty_feedback
from app.services.feedback_engine import (
    generate_hybrid_feedback,
    generate_slide_handoff_feedback,
    is_slide_handoff,
)
from app.services.llm_errors import classify_llm_error, log_llm_exception
from app.services.llm_feedback import generate_llm_feedback
from app.services.slide_inference import infer_current_slide
from app.services.student_profiles import update_student_profiles

router = APIRouter(tags=["analysis"])
logger = logging.getLogger("faculty_ai.analysis")
LIVE_LLM_MIN_GAP_SECONDS = 20
LIVE_LLM_BACKOFF_SECONDS = 90
NEW_SLIDE_WARMUP_CHUNKS = 4
HIGH_PRIORITY_MIN_SECONDS_ON_SLIDE = 12
MEDIUM_PRIORITY_MIN_SECONDS_ON_SLIDE = 18
LOW_PRIORITY_MIN_SECONDS_ON_SLIDE = 24
QUEUED_RELEASE_MIN_SECONDS_ON_SLIDE = 14


def _normalize_chunk(text: str) -> str:
    return " ".join(text.lower().split())


def _priority_rank(priority: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(priority, 0)


def _feedback_key(item: FeedbackItem) -> str:
    return item.sourceQuestionId or _normalize_message(item.message)


def _seconds_on_current_slide(session: dict) -> float:
    slide_started_at = session.get("slide_started_at")
    if not slide_started_at:
        return 0
    return max(0.0, (utc_now() - slide_started_at).total_seconds())


def _llm_backoff_active(session: dict) -> bool:
    backoff_until = session.get("llm_backoff_until")
    return bool(backoff_until and utc_now() < backoff_until)


def _can_attempt_live_llm(session: dict) -> bool:
    if _llm_backoff_active(session):
        return False
    last_attempt_at = session.get("last_llm_attempt_at")
    if not last_attempt_at:
        return True
    return (utc_now() - last_attempt_at).total_seconds() >= LIVE_LLM_MIN_GAP_SECONDS


def _mark_live_llm_attempt(session: dict) -> None:
    session["last_llm_attempt_at"] = utc_now()


def _mark_live_llm_backoff(session: dict) -> None:
    session["llm_backoff_until"] = utc_now() + timedelta(seconds=LIVE_LLM_BACKOFF_SECONDS)


def _find_slide(slides, slide_number: int | None):
    if slide_number is None:
        return None
    return next((slide for slide in slides if slide.slideNumber == slide_number), None)


def _slide_already_has_feedback(session: dict, slide_number: int | None) -> bool:
    if slide_number is None:
        return False
    return any(item.slideNumber == slide_number for item in session.get("feedback", []))


def _feedback_topic_key(item) -> str | None:
    source = (getattr(item, "sourceQuestionId", None) or "").lower()
    message = _normalize_message(getattr(item, "message", ""))

    if "team-perspective" in source:
        return "takeaways-team-perspective"
    if "individual-application" in source:
        return "individual-application"
    if "course-cip" in source:
        return "course-improvement"
    if "team-feedback" in source:
        return "team-feedback"
    if "architecture" in source:
        return "architecture"
    if "evaluation" in source:
        return "evaluation"
    if "problem-evidence" in source:
        return "problem-evidence"
    if "ai-specificity" in source:
        return "ai-specificity"

    if any(term in message for term in ["professionalism expectation", "enes 104 sessions", "why that one first"]):
        return "cip-course-professionalism"
    if any(term in message for term in ["little collaboration", "teambuilding workshop", "team-building workshop"]):
        return "cip-team-collaboration"
    if any(term in message for term in ["teammate feedback", "changed the final presentation", "accept it"]):
        return "team-feedback"
    if any(term in message for term in ["single most important lesson", "future engineering projects"]):
        return "closing-synthesis"

    if any(term in message for term in ["most important enes 104 takeaway", "team disagree", "disagreement shape this slide"]):
        return "takeaways-team-perspective"
    if any(term in message for term in ["professionalism", "perseverance", "key takeaways", "lessons to prioritize", "most impactful for future engineers"]):
        return "takeaways-team-perspective"
    if any(term in message for term in ["view of engineering", "specific experience caused", "change next because of that lesson"]):
        return "individual-application"
    if any(term in message for term in ["good enough", "lowquality work", "low quality work"]):
        return "individual-good-enough-distinction"
    if any(term in message for term in ["management could only act on one improvement", "next enes 104 student's experience"]):
        return "course-improvement"
    if any(term in message for term in ["architecture", "simpler alternative"]):
        return "architecture"
    if any(term in message for term in ["what metric will show", "metric supports the claim"]):
        return "evaluation"
    if any(term in message for term in ["real problem for the target users", "evidence shows this is a real problem"]):
        return "problem-evidence"
    if any(term in message for term in ["what exactly does the ai decide", "what input does it use"]):
        return "ai-specificity"
    return None


def _topic_already_covered(session: dict, candidate) -> bool:
    candidate_topic = _feedback_topic_key(candidate)
    if not candidate_topic:
        return False
    return any(_feedback_topic_key(item) == candidate_topic for item in session.get("feedback", []))


def _queued_feedback_duplicate_reason(session: dict, candidate: FeedbackItem) -> str | None:
    normalized_message = _normalize_message(candidate.message)
    if normalized_message in session.get("asked_feedback_messages", []):
        return "This faculty question was already asked earlier in the session."

    if candidate.sourceQuestionId and candidate.sourceQuestionId in session.get("asked_feedback_question_ids", []):
        return "This prepared faculty concern was already asked earlier in the session."

    if any(_normalize_message(item.message) == normalized_message for item in session.get("feedback", [])):
        return "This faculty question is already in the feedback history."

    if candidate.sourceQuestionId and any(item.sourceQuestionId == candidate.sourceQuestionId for item in session.get("feedback", [])):
        return "This prepared faculty concern is already in the feedback history."

    if _topic_already_covered(session, candidate):
        return "A faculty question on this same topic was already asked earlier in the session."

    return None


def _response(
    session: dict,
    *,
    trigger: bool,
    feedback: FeedbackItem | None = None,
    resolved_feedback: FeedbackItem | None = None,
    reason: str | None = None,
    inferred_current_slide=None,
    answer_evaluation=None,
) -> AnalyzeChunkResponse:
    return AnalyzeChunkResponse(
        trigger=trigger,
        feedback=feedback,
        queuedFeedback=session.get("queued_feedback"),
        resolvedFeedback=resolved_feedback,
        answerEvaluation=answer_evaluation,
        reason=reason,
        inferredCurrentSlide=inferred_current_slide,
    )


def _queue_feedback(session: dict, candidate: FeedbackItem, queue_reason: str) -> FeedbackItem:
    queued = candidate.model_copy(
        update={
            "deliveryStatus": "queued",
            "reason": queue_reason,
        }
    )
    existing = session.get("queued_feedback")
    if existing is None:
        session["queued_feedback"] = queued
        return queued

    if _feedback_key(existing) == _feedback_key(queued):
        return existing

    # Keep the stronger pending concern if multiple candidates collide before
    # the presenter reaches a clean moment for delivery.
    if _priority_rank(queued.priority) > _priority_rank(existing.priority):
        session["queued_feedback"] = queued
        return queued

    return existing


def _activate_queued_feedback(
    session: dict,
    *,
    current_slide_number: int | None,
    slide_chunk_count: int,
    handoff_detected: bool,
) -> tuple[FeedbackItem | None, str]:
    queued = session.get("queued_feedback")
    if queued is None:
        return None, "No queued faculty question is waiting."

    if queued.slideNumber is not None and current_slide_number is not None and queued.slideNumber != current_slide_number:
        session["queued_feedback"] = None
        return None, "Dropped stale queued question after the presentation moved to a different slide."

    awaiting_answer_until = session.get("awaiting_answer_until")
    if awaiting_answer_until and utc_now() < awaiting_answer_until:
        return None, "Queued faculty question is waiting for the current answer window to finish."

    seconds_on_slide = _seconds_on_current_slide(session)
    if slide_chunk_count < NEW_SLIDE_WARMUP_CHUNKS and seconds_on_slide < QUEUED_RELEASE_MIN_SECONDS_ON_SLIDE and not handoff_detected:
        return None, "Queued faculty question is waiting for enough spoken context and time on the slide."

    duplicate_reason = _queued_feedback_duplicate_reason(session, queued)
    if duplicate_reason is not None:
        session["queued_feedback"] = None
        return None, f"Dropped queued faculty question because {duplicate_reason[0].lower()}{duplicate_reason[1:]}"

    allowed, filter_reason = can_emit_feedback(session, queued.message)
    if not allowed:
        if filter_reason.startswith("Cooldown active."):
            return None, "Queued faculty question is still waiting for the global cooldown to finish."
        session["queued_feedback"] = None
        return None, f"Dropped queued faculty question because {filter_reason[0].lower()}{filter_reason[1:]}"

    session["queued_feedback"] = None
    activated = queued.model_copy(update={"deliveryStatus": "active"})
    return activated, "Delivered a previously queued faculty question once timing conditions were safe."


def _record_feedback(session: dict, candidate: FeedbackItem, current_slide_number: int | None) -> None:
    candidate.deliveryStatus = "active"
    session["feedback"].append(candidate)
    session["last_feedback_at"] = utc_now()
    session.setdefault("asked_feedback_messages", []).append(_normalize_message(candidate.message))
    if candidate.sourceQuestionId:
        session.setdefault("asked_feedback_question_ids", []).append(candidate.sourceQuestionId)
    if current_slide_number is not None:
        session.setdefault("asked_feedback_slide_numbers", []).append(current_slide_number)
    if candidate.targetStudent:
        student_coverage = session.setdefault("student_coverage", {})
        student_coverage[candidate.targetStudent] = int(student_coverage.get(candidate.targetStudent, 0)) + 1
    session["awaiting_answer_until"] = utc_now() + timedelta(seconds=15)
    session["last_feedback_slide_number"] = current_slide_number


def _timing_gate_reason(session: dict, candidate: FeedbackItem, handoff_detected: bool) -> str | None:
    if handoff_detected:
        return None
    if session.get("active_slide_number") is None:
        return None

    seconds_on_slide = _seconds_on_current_slide(session)
    min_seconds = {
        "high": HIGH_PRIORITY_MIN_SECONDS_ON_SLIDE,
        "medium": MEDIUM_PRIORITY_MIN_SECONDS_ON_SLIDE,
        "low": LOW_PRIORITY_MIN_SECONDS_ON_SLIDE,
    }.get(candidate.priority, MEDIUM_PRIORITY_MIN_SECONDS_ON_SLIDE)

    if seconds_on_slide >= min_seconds:
        return None
    return (
        "Timing gate: waiting for the presenter to spend longer on the slide "
        f"before interrupting ({round(seconds_on_slide, 1)}s so far, target {min_seconds}s)."
    )


@router.post("/analyze-chunk", response_model=AnalyzeChunkResponse)
def analyze_chunk(payload: AnalyzeChunkRequest) -> AnalyzeChunkResponse:
    session = state.get_session(payload.sessionId)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Normalize and persist the chunk immediately so downstream reasoning works
    # against a stable session transcript and duplicate live events are ignored.
    normalized_chunk = _normalize_chunk(payload.transcriptChunk)
    if not normalized_chunk:
        return _response(session, trigger=False, reason="Transcript chunk is empty.")

    if session.get("last_transcript_chunk") == normalized_chunk:
        return _response(session, trigger=False, reason="Duplicate transcript chunk ignored.")

    session["last_transcript_chunk"] = normalized_chunk
    session["transcript"].append(payload.transcriptChunk)
    session["last_transcript_at"] = utc_now()
    state.save_session(payload.sessionId, session)
    previous_slide_number = session.get("active_slide_number")

    # Slide inference is intentionally conservative. Auto mode requires repeated
    # evidence before switching slides so a single noisy transcript chunk does
    # not thrash the active-slide context.
    if payload.slideMode == "manual":
        inferred_slide = payload.currentSlide
        session["candidate_slide_number"] = None
        session["candidate_slide_hits"] = 0
        effective_slide = payload.currentSlide
    elif previous_slide_number is None and payload.currentSlide is not None:
        inferred_slide = payload.currentSlide
        session["candidate_slide_number"] = None
        session["candidate_slide_hits"] = 0
        effective_slide = payload.currentSlide
    else:
        inferred_slide = infer_current_slide(
            " ".join([*payload.recentTranscript[-4:], payload.transcriptChunk]),
            payload.presentationSlides,
            payload.currentSlide.slideNumber if payload.currentSlide else session.get("active_slide_number"),
        )
        if inferred_slide and previous_slide_number and inferred_slide.slideNumber != previous_slide_number:
            if session.get("candidate_slide_number") == inferred_slide.slideNumber:
                session["candidate_slide_hits"] = int(session.get("candidate_slide_hits", 0)) + 1
            else:
                session["candidate_slide_number"] = inferred_slide.slideNumber
                session["candidate_slide_hits"] = 1

            if int(session.get("candidate_slide_hits", 0)) < 2:
                effective_slide = _find_slide(payload.presentationSlides, previous_slide_number) or payload.currentSlide
                inferred_slide = effective_slide
            else:
                session["candidate_slide_number"] = None
                session["candidate_slide_hits"] = 0
                effective_slide = inferred_slide
        else:
            session["candidate_slide_number"] = None
            session["candidate_slide_hits"] = 0
            effective_slide = inferred_slide or payload.currentSlide

    # Keep a per-slide warm-up counter so the backend can wait for enough spoken
    # context before interrupting on a newly active slide.
    current_slide_number = effective_slide.slideNumber if effective_slide else None
    slide_changed = current_slide_number is not None and current_slide_number != previous_slide_number
    if current_slide_number is None:
        session["active_slide_number"] = None
        session["active_slide_chunk_count"] = 0
    elif slide_changed:
        session["active_slide_number"] = current_slide_number
        session["active_slide_chunk_count"] = 1
        session["slide_started_at"] = utc_now()
    else:
        session["active_slide_number"] = current_slide_number
        session["active_slide_chunk_count"] = int(session.get("active_slide_chunk_count", 0)) + 1
        session["slide_started_at"] = session.get("slide_started_at") or utc_now()

    if payload.simulatedSecondsOnSlide is not None and current_slide_number is not None:
        # Eval replays run much faster than real speaking, so allow the harness
        # to inject simulated slide time without changing live behavior.
        session["slide_started_at"] = utc_now() - timedelta(seconds=max(0.0, payload.simulatedSecondsOnSlide))

    slide_chunk_count = int(session.get("active_slide_chunk_count", 0))
    handoff_detected = is_slide_handoff(payload.transcriptChunk)
    recent_feedback_messages = [item.message for item in session.get("feedback", [])][-5:]
    asked_messages = list(session.get("asked_feedback_messages", []))
    session["student_profiles"] = update_student_profiles(
        session.get("student_profiles", {}),
        payload.transcriptChunk,
        effective_slide,
    )
    runtime_student_profiles = session.get("student_profiles", {})
    state.save_session(payload.sessionId, session)

    resolved_feedback = None
    answer_evaluation = None
    follow_up_feedback = None
    latest_feedback_slide_number = session.get("last_feedback_slide_number")
    if (
        latest_feedback_slide_number is not None
        and current_slide_number == latest_feedback_slide_number
    ):
        resolved_feedback, answer_evaluation, follow_up_feedback = evaluate_latest_feedback_answer(
            feedback_items=session.get("feedback", []),
            transcript_chunk=payload.transcriptChunk,
            recent_transcript=payload.recentTranscript,
            prepared_questions=payload.preparedQuestions,
            follow_up_attempts=session.get("follow_up_attempts", {}),
        )

    if resolved_feedback:
        session["awaiting_answer_until"] = None
        state.save_session(payload.sessionId, session)
        return _response(
            session,
            trigger=False,
            resolved_feedback=resolved_feedback,
            reason=resolved_feedback.resolutionReason,
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    if follow_up_feedback is not None:
        session.setdefault("follow_up_attempts", {})[follow_up_feedback.followUpToQuestionId or follow_up_feedback.createdAt] = 1
        _queue_feedback(
            session,
            follow_up_feedback,
            (
                "Queued one follow-up because the presenter partially answered the earlier faculty concern. "
                f"Still missing: {', '.join(answer_evaluation.missingPoints) if answer_evaluation else 'key detail'}."
            ),
        )
        state.save_session(payload.sessionId, session)
        return _response(
            session,
            trigger=False,
            reason="Partial presenter answer detected. FacultyAI queued one follow-up rather than interrupting immediately.",
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    queued_candidate, queued_reason = _activate_queued_feedback(
        session,
        current_slide_number=current_slide_number,
        slide_chunk_count=slide_chunk_count,
        handoff_detected=handoff_detected,
    )
    if queued_candidate is not None:
        _record_feedback(session, queued_candidate, current_slide_number)
        state.save_session(payload.sessionId, session)
        logger.info(
            "triggered queued feedback session=%s slide=%s source=%s",
            payload.sessionId[:8],
            current_slide_number,
            queued_candidate.sourceQuestionId or "heuristic",
        )
        return _response(
            session,
            trigger=True,
            feedback=queued_candidate,
            reason=queued_reason,
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    # Candidate selection is layered from cheapest/safest to most expensive:
    # slide handoff heuristics, slide-aware prepared questions, optional LLM
    # arbitration, then a final generic fallback if nothing else matches.
    candidate, reason = generate_slide_handoff_feedback(
        payload.transcriptChunk,
        recent_transcript=payload.recentTranscript,
        prepared_questions=payload.preparedQuestions,
        current_slide_number=current_slide_number,
        asked_question_ids=list(session.get("asked_feedback_question_ids", [])),
        current_slide=effective_slide,
        project_title=payload.projectContext.title,
        student_profiles=runtime_student_profiles,
    )

    if candidate is None and slide_chunk_count >= NEW_SLIDE_WARMUP_CHUNKS:
        candidate, reason = generate_hybrid_feedback(
            payload.transcriptChunk,
            recent_transcript=payload.recentTranscript,
            prepared_questions=payload.preparedQuestions,
            current_slide=effective_slide,
            project_title=payload.projectContext.title,
            student_profiles=runtime_student_profiles,
        )

    if candidate is None and slide_chunk_count >= NEW_SLIDE_WARMUP_CHUNKS and _can_attempt_live_llm(session):
        _mark_live_llm_attempt(session)
        state.save_session(payload.sessionId, session)
        try:
            # The faculty-brain path is used as an arbiter over prepared
            # questions, not as a general-purpose source of new harsher prompts.
            faculty_brain = decide_faculty_feedback(
                payload=payload.model_copy(
                    update={
                        "studentCoverage": session.get("student_coverage", {}),
                        "studentProfiles": runtime_student_profiles,
                    }
                ),
                current_slide=effective_slide,
                recent_feedback=recent_feedback_messages,
                asked_messages=asked_messages,
            )
        except Exception as exc:
            log_llm_exception("decide_faculty_feedback", exc)
            classified = classify_llm_error(exc)
            if "rate limit" in classified.lower() or "429" in classified:
                _mark_live_llm_backoff(session)
                state.save_session(payload.sessionId, session)
            faculty_brain = None

        if faculty_brain and faculty_brain.terminal:
            if faculty_brain.feedback is None:
                return _response(
                    session,
                    trigger=False,
                    reason=faculty_brain.reason,
                    inferred_current_slide=inferred_slide,
                    answer_evaluation=answer_evaluation,
                )
            candidate, reason = faculty_brain.feedback, faculty_brain.reason
        elif candidate is None and not payload.preparedQuestions:
            llm_result = None
            try:
                llm_result = generate_llm_feedback(payload)
            except Exception as exc:
                log_llm_exception("generate_llm_feedback", exc)
                classified = classify_llm_error(exc)
                if "rate limit" in classified.lower() or "429" in classified:
                    _mark_live_llm_backoff(session)
                    state.save_session(payload.sessionId, session)
                reason = f"LLM fallback failed: {classified}"

            if llm_result is not None:
                candidate, reason = llm_result

    elif candidate is None and _llm_backoff_active(session):
        reason = "LLM backoff active after provider rate limit. Using deterministic faculty logic only."

    if candidate is None:
        state.save_session(payload.sessionId, session)
        return _response(
            session,
            trigger=False,
            reason=reason or queued_reason,
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    normalized_message = _normalize_message(candidate.message)
    if normalized_message in session.get("asked_feedback_messages", []):
        return _response(
            session,
            trigger=False,
            reason="This faculty question was already asked earlier in the session.",
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    if candidate.sourceQuestionId and candidate.sourceQuestionId in session.get("asked_feedback_question_ids", []):
        return _response(
            session,
            trigger=False,
            reason="This prepared faculty concern was already asked earlier in the session.",
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    if any(_normalize_message(item.message) == normalized_message for item in session.get("feedback", [])):
        return _response(
            session,
            trigger=False,
            reason="This faculty question is already in the feedback history.",
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    if candidate.sourceQuestionId and any(item.sourceQuestionId == candidate.sourceQuestionId for item in session.get("feedback", [])):
        return _response(
            session,
            trigger=False,
            reason="This prepared faculty concern is already in the feedback history.",
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    if _topic_already_covered(session, candidate):
        return _response(
            session,
            trigger=False,
            reason="A faculty question on this same topic was already asked earlier in the session.",
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    if _slide_already_has_feedback(session, current_slide_number):
        return _response(
            session,
            trigger=False,
            reason="This slide already received its one faculty question for this presentation.",
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    timing_gate_reason = _timing_gate_reason(session, candidate, handoff_detected)
    if slide_changed and not handoff_detected:
        _queue_feedback(
            session,
            candidate,
            "Queued until the presenter gives more context on the new slide before FacultyAI interrupts.",
        )
        state.save_session(payload.sessionId, session)
        return _response(
            session,
            trigger=False,
            reason="Slide warm-up: FacultyAI queued the question instead of interrupting on slide arrival.",
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    if timing_gate_reason is not None:
        _queue_feedback(session, candidate, timing_gate_reason)
        state.save_session(payload.sessionId, session)
        return _response(
            session,
            trigger=False,
            reason=timing_gate_reason,
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    # Let the presenter establish context before lower-priority interruptions fire.
    if len(session["transcript"]) < 2 and candidate.priority == "low":
        state.save_session(payload.sessionId, session)
        return _response(
            session,
            trigger=False,
            reason="Warm-up window: waiting for more live context before interrupting.",
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    # Once a question has been asked on the active slide, hold a short answer
    # window before allowing another interruption on that same slide.
    awaiting_answer_until = session.get("awaiting_answer_until")
    if awaiting_answer_until and utc_now() < awaiting_answer_until and session.get("last_feedback_slide_number") == current_slide_number:
        _queue_feedback(
            session,
            candidate,
            "Queued while FacultyAI waits for the presenter to finish answering the earlier question.",
        )
        state.save_session(payload.sessionId, session)
        return _response(
            session,
            trigger=False,
            reason="Answer window active: FacultyAI queued the next question instead of stacking interruptions.",
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    # Older sessions may still rely on the side-list. Trim any stale entries once
    # the feedback history says this slide has not actually been asked yet.
    if current_slide_number is not None and current_slide_number in session.get("asked_feedback_slide_numbers", []):
        session["asked_feedback_slide_numbers"] = [
            number
            for number in session.get("asked_feedback_slide_numbers", [])
            if _slide_already_has_feedback(session, number)
        ]

    # The cooldown filter is the final global safety gate after all slide/topic
    # checks pass. It prevents the live experience from feeling spammy even if
    # the transcript repeatedly matches valid faculty concerns.
    allowed, filter_reason = can_emit_feedback(session, candidate.message)
    if not allowed:
        _queue_feedback(
            session,
            candidate,
            f"Queued because the global feedback cooldown blocked immediate delivery. {filter_reason}",
        )
        state.save_session(payload.sessionId, session)
        return _response(
            session,
            trigger=False,
            reason=filter_reason,
            inferred_current_slide=inferred_slide,
            answer_evaluation=answer_evaluation,
        )

    _record_feedback(session, candidate, current_slide_number)
    state.save_session(payload.sessionId, session)
    logger.info(
        "triggered feedback session=%s slide=%s source=%s reason=%s",
        payload.sessionId[:8],
        current_slide_number,
        candidate.sourceQuestionId or "heuristic",
        reason,
    )
    return _response(
        session,
        trigger=True,
        feedback=candidate,
        reason=reason,
        inferred_current_slide=inferred_slide,
        answer_evaluation=answer_evaluation,
    )
