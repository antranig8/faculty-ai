from datetime import timezone
from typing import Optional

from app.models.response_models import PreparedQuestion
from app.models.response_models import FeedbackItem
from app.services.cooldown import utc_now
from app.services.section_tracker import infer_section

VAGUE_TERMS = ["better", "efficient", "improve", "personalized", "adaptive", "smart", "easy"]
CLAIM_TERMS = ["increase", "decrease", "faster", "more accurate", "better", "improve", "optimize"]
TECH_TERMS = ["react", "next", "fastapi", "python", "api", "database", "supabase", "model", "llm"]


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _mentions_metric(text: str) -> bool:
    metric_markers = ["%", "percent", "metric", "measured", "evaluated", "tested", "survey", "baseline"]
    return _contains_any(text, metric_markers)


def _question_matches_transcript(question: PreparedQuestion, text: str) -> bool:
    lower_text = text.lower()
    return any(term.lower() in lower_text for term in question.listenFor)


def _concern_is_unanswered(question: PreparedQuestion, recent_text: str) -> bool:
    lower_recent = recent_text.lower()
    return not any(marker.lower() in lower_recent for marker in question.missingIfAbsent)


def _created_at() -> str:
    return utc_now().astimezone(timezone.utc).isoformat()


def generate_candidate_feedback(text: str, project_title: str = "") -> tuple[Optional[FeedbackItem], str]:
    words = text.split()
    if len(words) < 12:
        return None, "Transcript chunk is too short to evaluate."

    lower_text = text.lower()
    section = infer_section(text)
    title = project_title.strip() or "this project"

    if _contains_any(lower_text, CLAIM_TERMS) and not _mentions_metric(lower_text):
        return FeedbackItem(
            type="question",
            priority="medium",
            section=section,
            message=f"What metric supports the claim you just made about {title}?",
            reason="The presenter made an improvement or performance claim without evidence.",
            createdAt=_created_at(),
        ), "Generated feedback for an unsupported claim."

    if _contains_any(lower_text, TECH_TERMS) and not _contains_any(lower_text, ["because", "chosen", "tradeoff", "alternative", "instead"]):
        return FeedbackItem(
            type="critique",
            priority="medium",
            section=section,
            message="The stack is named, but the reason for choosing it over alternatives is still missing.",
            reason="A technical choice was mentioned without a clear justification.",
            createdAt=_created_at(),
        ), "Generated feedback for an unjustified technical choice."

    if _contains_any(lower_text, ["personalized", "adaptive", "custom", "tailored"]):
        return FeedbackItem(
            type="clarification",
            priority="medium",
            section=section,
            message="What exactly changes for each user, and what input controls that change?",
            reason="Personalization was mentioned but the mechanism is not yet specific.",
            createdAt=_created_at(),
        ), "Generated feedback for vague personalization."

    if _contains_any(lower_text, VAGUE_TERMS):
        return FeedbackItem(
            type="suggestion",
            priority="low",
            section=section,
            message="Replace the broad claim with one concrete example or measurable outcome.",
            reason="The chunk uses broad language that would be stronger with a specific example.",
            createdAt=_created_at(),
        ), "Generated feedback for vague language."

    if section == "problem" and _contains_any(lower_text, ["users", "students", "people"]) and not _contains_any(lower_text, ["interview", "survey", "observed", "evidence"]):
        return FeedbackItem(
            type="question",
            priority="medium",
            section=section,
            message="What evidence shows this is a real problem for your target users?",
            reason="The problem is described, but the source of evidence is unclear.",
            createdAt=_created_at(),
        ), "Generated feedback for problem validation."

    return None, "No high-value feedback trigger found."


def generate_slide_aware_feedback(
    text: str,
    recent_transcript: list[str],
    prepared_questions: list[PreparedQuestion],
    current_slide_number: int | None,
) -> tuple[Optional[FeedbackItem], str]:
    words = text.split()
    if len(words) < 8:
        return None, "Transcript chunk is too short for slide-aware feedback."

    relevant_questions = [
        question
        for question in prepared_questions
        if current_slide_number is None or question.slideNumber == current_slide_number
    ]
    recent_text = " ".join([*recent_transcript[-4:], text])
    section = infer_section(recent_text)

    for question in sorted(relevant_questions, key=lambda item: {"high": 0, "medium": 1, "low": 2}[item.priority]):
        if question.priority == "low" and len(recent_transcript) < 3:
            continue
        if not _question_matches_transcript(question, recent_text):
            continue

        if not _concern_is_unanswered(question, recent_text):
            continue

        return FeedbackItem(
            type=question.type,
            priority=question.priority,
            section=section,
            message=question.question,
            reason=f"Rubric focus: {question.rubricCategory}. The current slide raised this issue, but the spoken explanation has not addressed it yet.",
            createdAt=_created_at(),
        ), "Generated feedback from prepared slide question."

    return None, "No prepared slide question matched an unanswered concern."
