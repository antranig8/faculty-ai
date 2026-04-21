from app.models.response_models import FeedbackItem, PreparedQuestion
from app.services.cooldown import utc_now


EVIDENCE_TERMS = ["survey", "interview", "observed", "evidence", "research", "data", "feedback", "tested", "study"]
METRIC_TERMS = ["metric", "baseline", "measured", "tested", "result", "accuracy", "percent", "%", "seconds", "users"]
TRADEOFF_TERMS = ["because", "tradeoff", "trade-off", "alternative", "instead", "compared", "chosen", "we chose", "we picked"]
MECHANISM_TERMS = ["input", "output", "decide", "model", "prompt", "data", "uses", "based on"]


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term.lower() in text for term in terms)


def _terms_from_question(feedback: FeedbackItem, prepared_questions: list[PreparedQuestion]) -> list[str]:
    if feedback.autoResolutionTerms:
        return feedback.autoResolutionTerms

    if feedback.sourceQuestionId:
        match = next((question for question in prepared_questions if question.id == feedback.sourceQuestionId), None)
        if match:
            return match.missingIfAbsent

    normalized_message = _normalize(feedback.message)
    match = next((question for question in prepared_questions if _normalize(question.question) == normalized_message), None)
    return match.missingIfAbsent if match else []


def _fallback_terms_for_message(message: str) -> list[str]:
    lowered = _normalize(message)
    terms: list[str] = []
    if any(term in lowered for term in ["architecture", "stack", "choice", "alternative", "chosen"]):
        terms.extend(TRADEOFF_TERMS)
    if any(term in lowered for term in ["metric", "works", "claim", "measurable", "outcome"]):
        terms.extend(METRIC_TERMS)
    if any(term in lowered for term in ["evidence", "problem", "target users", "real problem"]):
        terms.extend(EVIDENCE_TERMS)
    if any(term in lowered for term in ["ai", "input", "decide", "personalized", "changes for each user"]):
        terms.extend(MECHANISM_TERMS)
    return terms


def _answer_quality_score(answer_text: str, feedback: FeedbackItem, prepared_questions: list[PreparedQuestion]) -> tuple[int, list[str]]:
    normalized_answer = _normalize(answer_text)
    if len(normalized_answer.split()) < 6:
        return 0, []

    terms = [*_terms_from_question(feedback, prepared_questions), *_fallback_terms_for_message(feedback.message)]
    matched_terms: list[str] = []
    for term in terms:
        normalized_term = _normalize(term)
        if normalized_term and normalized_term in normalized_answer and normalized_term not in matched_terms:
            matched_terms.append(normalized_term)

    score = len(matched_terms) * 2
    if _contains_any(normalized_answer, EVIDENCE_TERMS):
        score += 2
    if _contains_any(normalized_answer, METRIC_TERMS):
        score += 2
    if _contains_any(normalized_answer, TRADEOFF_TERMS):
        score += 2
    if _contains_any(normalized_answer, MECHANISM_TERMS):
        score += 1

    return score, matched_terms[:4]


def resolve_latest_feedback_if_answered(
    feedback_items: list[FeedbackItem],
    transcript_chunk: str,
    recent_transcript: list[str],
    prepared_questions: list[PreparedQuestion],
) -> FeedbackItem | None:
    unresolved = [item for item in feedback_items if not item.resolved]
    if not unresolved:
        return None

    latest = unresolved[-1]
    answer_text = " ".join([*recent_transcript[-2:], transcript_chunk])
    score, matched_terms = _answer_quality_score(answer_text, latest, prepared_questions)
    if score < 4:
        return None

    latest.resolved = True
    latest.resolvedAt = utc_now().isoformat()
    latest.resolutionReason = (
        "Auto-resolved from presenter response"
        + (f" mentioning {', '.join(matched_terms)}." if matched_terms else ".")
    )
    return latest
