from datetime import timezone
from typing import Optional

from app.models.response_models import PreparedQuestion
from app.models.response_models import FeedbackItem
from app.services.cooldown import utc_now
from app.services.question_matching import meaningful_listen_terms, prepared_question_is_topically_ready
from app.services.section_tracker import infer_section

VAGUE_TERMS = ["better", "efficient", "improve", "personalized", "adaptive", "smart", "easy"]
CLAIM_TERMS = ["increase", "decrease", "faster", "more accurate", "better", "improve", "optimize"]
TECH_TERMS = ["react", "next", "fastapi", "python", "api", "database", "supabase", "model", "llm"]
SLIDE_HANDOFF_TERMS = [
    "any questions",
    "questions",
    "does anyone have questions",
    "do you have questions",
    "are there any questions",
    "that's it",
    "that is it",
]


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _mentions_metric(text: str) -> bool:
    metric_markers = ["%", "percent", "metric", "measured", "evaluated", "tested", "survey", "baseline"]
    return _contains_any(text, metric_markers)


def _question_matches_transcript(question: PreparedQuestion, text: str) -> bool:
    return prepared_question_is_topically_ready(question, text)


def _concern_is_unanswered(question: PreparedQuestion, recent_text: str) -> bool:
    lower_recent = recent_text.lower()
    return not any(marker.lower() in lower_recent for marker in question.missingIfAbsent)


def _question_is_proactively_ready(question: PreparedQuestion, recent_text: str, recent_transcript: list[str]) -> bool:
    if question.priority == "low":
        return False

    normalized_recent = recent_text.lower()
    listen_terms = meaningful_listen_terms(question)
    if any(term in normalized_recent for term in listen_terms):
        return True

    # Prepared concerns are already scoped to the inferred slide. After enough
    # speech on that slide, surface the strongest missing concern before the
    # presenter explicitly asks for questions.
    word_count = len(recent_text.split())
    if question.priority == "high":
        return word_count >= 18
    return question.priority == "medium" and word_count >= 32


def _created_at() -> str:
    return utc_now().astimezone(timezone.utc).isoformat()


def is_slide_handoff(text: str) -> bool:
    lower_text = text.lower()
    return any(term in lower_text for term in SLIDE_HANDOFF_TERMS)


def _feedback_from_prepared_question(question: PreparedQuestion, section: str, reason: str) -> FeedbackItem:
    return FeedbackItem(
        type=question.type,
        priority=question.priority,
        section=section,
        message=question.question,
        reason=f"Rubric focus: {question.rubricCategory}. {reason}",
        createdAt=_created_at(),
        sourceQuestionId=question.id,
        autoResolutionTerms=question.missingIfAbsent[:8],
    )


def generate_slide_handoff_feedback(
    text: str,
    recent_transcript: list[str],
    prepared_questions: list[PreparedQuestion],
    current_slide_number: int | None,
    asked_question_ids: list[str],
) -> tuple[Optional[FeedbackItem], str]:
    if not is_slide_handoff(text):
        return None, "No end-of-slide question handoff detected."

    relevant_questions = [
        question
        for question in prepared_questions
        if (current_slide_number is None or question.slideNumber == current_slide_number)
        and question.id not in asked_question_ids
    ]
    if not relevant_questions:
        return None, "No unasked prepared concern exists for this slide."

    recent_text = " ".join([*recent_transcript[-4:], text])
    section = infer_section(recent_text)
    for question in sorted(relevant_questions, key=lambda item: {"high": 0, "medium": 1, "low": 2}[item.priority]):
        if not _concern_is_unanswered(question, recent_text):
            continue
        return _feedback_from_prepared_question(
            question=question,
            section=section,
            reason="The presenter invited questions at the end of the slide, so FacultyAI surfaced the strongest unasked prepared concern.",
        ), "Generated end-of-slide faculty question from prepared concerns."

    return None, "Prepared concerns for this slide were already addressed before the question handoff."


def generate_candidate_feedback(text: str, project_title: str = "") -> tuple[Optional[FeedbackItem], str]:
    words = text.split()
    if len(words) < 12:
        return None, "Transcript chunk is too short to evaluate."

    lower_text = text.lower()
    section = infer_section(text)
    title = project_title.strip() or "this project"

    if _contains_any(lower_text, ["takeaway", "takeaways"]) and not _contains_any(lower_text, ["perspective", "because", "we chose", "our group", "most important"]):
        return FeedbackItem(
            type="question",
            priority="high",
            section=section,
            message="Where did your team disagree about the most important ENES 104 takeaway, and how did that disagreement shape this slide?",
            reason="The presenter discussed takeaways but has not yet distinguished team perspective from summary.",
            createdAt=_created_at(),
        ), "Generated Assignment 6 feedback for team perspective."

    if _contains_any(lower_text, ["lesson", "lessons", "learned", "workshop", "speaker"]) and not _contains_any(lower_text, ["apply", "future", "career", "use this", "engineering practice"]):
        return FeedbackItem(
            type="question",
            priority="high",
            section=section,
            message="What changed in your view of engineering because of this lesson, and what specific experience caused that change?",
            reason="The presenter mentioned a lesson but has not yet connected it to individual application.",
            createdAt=_created_at(),
        ), "Generated Assignment 6 feedback for individual application."

    if _contains_any(lower_text, ["cip", "continuous improvement", "what worked", "improve"]) and not _contains_any(lower_text, ["management", "priority", "because", "specific"]):
        return FeedbackItem(
            type="question",
            priority="high",
            section=section,
            message="If management could only act on one improvement, which one would most change the next ENES 104 student's experience?",
            reason="The presenter discussed continuous improvement without a clear priority or rationale.",
            createdAt=_created_at(),
        ), "Generated Assignment 6 feedback for course improvement planning."

    if _contains_any(lower_text, ["teamwork", "team work", "team building", "team-building", "feedback"]) and not _contains_any(lower_text, ["changed", "improved", "specific", "each other", "how"]):
        return FeedbackItem(
            type="question",
            priority="high",
            section=section,
            message="What is one piece of teammate feedback that actually changed the final presentation, and why did you accept it?",
            reason="The presenter referenced teamwork or feedback without explaining the exchange and impact.",
            createdAt=_created_at(),
        ), "Generated Assignment 6 feedback for team feedback."

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
        if question.priority == "low" and len(recent_transcript) < 2:
            continue
        if not _question_matches_transcript(question, recent_text):
            if not _question_is_proactively_ready(question, recent_text, recent_transcript):
                continue

        if not _concern_is_unanswered(question, recent_text):
            continue

        return _feedback_from_prepared_question(
            question=question,
            section=section,
            reason="The current slide has enough spoken context for this prepared concern, but the explanation has not addressed it yet.",
        ), "Generated proactive feedback from prepared slide question."

    return None, "No prepared slide question matched an unanswered concern."
