from app.models.response_models import AnswerEvaluation, FeedbackItem, PreparedQuestion
from app.services.cooldown import _normalize_message, utc_now


EVIDENCE_TERMS = ["survey", "interview", "observed", "evidence", "research", "data", "feedback", "tested", "study"]
METRIC_TERMS = ["metric", "baseline", "measured", "tested", "result", "accuracy", "percent", "%", "seconds", "users"]
TRADEOFF_TERMS = ["because", "tradeoff", "trade-off", "alternative", "instead", "compared", "chosen", "we chose", "we picked"]
MECHANISM_TERMS = ["input", "output", "decide", "model", "prompt", "data", "uses", "based on"]


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term.lower() in text for term in terms)


def _feedback_key(feedback: FeedbackItem) -> str:
    return feedback.sourceQuestionId or _normalize_message(feedback.message)


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


def _ordered_terms(feedback: FeedbackItem, prepared_questions: list[PreparedQuestion]) -> list[str]:
    # Keep order stable so the evaluator can describe the missing points in a
    # way that stays close to the original prepared concern.
    ordered: list[str] = []
    for term in [*_terms_from_question(feedback, prepared_questions), *_fallback_terms_for_message(feedback.message)]:
        clean_term = term.strip()
        if clean_term and clean_term not in ordered:
            ordered.append(clean_term)
    return ordered


def _answer_quality_score(answer_text: str, feedback: FeedbackItem, prepared_questions: list[PreparedQuestion]) -> tuple[int, list[str], list[str]]:
    normalized_answer = _normalize(answer_text)
    if len(normalized_answer.split()) < 6:
        return 0, [], _ordered_terms(feedback, prepared_questions)[:3]

    matched_terms: list[str] = []
    ordered_terms = _ordered_terms(feedback, prepared_questions)
    for term in ordered_terms:
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

    missing_terms = [
        term
        for term in ordered_terms
        if _normalize(term) not in matched_terms
    ]
    return score, matched_terms[:4], missing_terms[:3]


def _follow_up_message(feedback: FeedbackItem, missing_points: list[str]) -> str:
    lowered = _normalize(feedback.message)
    first_missing = (missing_points[0] if missing_points else "").strip()
    if any(term in lowered for term in ["metric", "claim", "works", "outcome"]):
        return "What specific metric or result supports that claim?"
    if any(term in lowered for term in ["evidence", "target users", "real problem"]):
        return "What specific evidence supports that point?"
    if any(term in lowered for term in ["architecture", "stack", "alternative", "chosen"]):
        return "What was the main reason for that choice compared with the alternative?"
    if any(term in lowered for term in ["lesson", "future", "career", "apply", "change"]):
        return "What concrete change will you make in your future engineering work because of that lesson?"
    if first_missing:
        return f"What specifically can you add about {first_missing}?"
    return "What specific missing point should the audience hear to justify that answer?"


def evaluate_latest_feedback_answer(
    feedback_items: list[FeedbackItem],
    transcript_chunk: str,
    recent_transcript: list[str],
    prepared_questions: list[PreparedQuestion],
    follow_up_attempts: dict[str, int],
) -> tuple[FeedbackItem | None, AnswerEvaluation | None, FeedbackItem | None]:
    unresolved = [item for item in feedback_items if not item.resolved and item.deliveryStatus == "active"]
    if not unresolved:
        return None, None, None

    latest = unresolved[-1]
    answer_text = " ".join([*recent_transcript[-2:], transcript_chunk])
    score, matched_terms, missing_terms = _answer_quality_score(answer_text, latest, prepared_questions)
    is_follow_up = bool(latest.followUpToQuestionId)

    if score >= 6 or (len(matched_terms) >= 2 and len(missing_terms) <= 1):
        latest.resolved = True
        latest.deliveryStatus = "resolved"
        latest.answerQuality = "strong"
        latest.resolvedAt = utc_now().isoformat()
        latest.resolutionReason = (
            "Auto-resolved from presenter response"
            + (f" mentioning {', '.join(matched_terms)}." if matched_terms else ".")
        )
        evaluation = AnswerEvaluation(
            questionId=latest.sourceQuestionId or latest.createdAt,
            answered=True,
            answerQuality="strong",
            missingPoints=missing_terms,
        )
        return latest, evaluation, None

    if score >= 3 or matched_terms:
        question_key = _feedback_key(latest)
        # Allow at most one queued follow-up for the original faculty question.
        # Once the active item is itself a follow-up, evaluate it but do not
        # recursively spawn follow-ups from follow-ups.
        should_follow_up = (not is_follow_up) and follow_up_attempts.get(question_key, 0) < 1 and bool(missing_terms)
        follow_up = None
        follow_up_message = None
        if should_follow_up:
            follow_up_message = _follow_up_message(latest, missing_terms)
            follow_up = FeedbackItem(
                type="clarification",
                priority=latest.priority,
                section=latest.section,
                message=follow_up_message,
                reason=(
                    "Follow-up queued because the presenter addressed part of the concern, "
                    f"but the explanation still missed {', '.join(missing_terms)}."
                ),
                createdAt=utc_now().isoformat(),
                slideNumber=latest.slideNumber,
                sourceQuestionId=f"{latest.sourceQuestionId or latest.createdAt}:follow-up-1",
                autoResolutionTerms=missing_terms[:3],
                deliveryStatus="queued",
                followUpToQuestionId=question_key,
                targetStudent=latest.targetStudent,
            )

        evaluation = AnswerEvaluation(
            questionId=latest.sourceQuestionId or latest.createdAt,
            answered=True,
            answerQuality="partial",
            missingPoints=missing_terms,
            shouldAskFollowUp=should_follow_up,
            followUpQuestion=follow_up_message,
        )
        latest.answerQuality = "partial"
        return None, evaluation, follow_up

    evaluation = AnswerEvaluation(
        questionId=latest.sourceQuestionId or latest.createdAt,
        answered=False,
        answerQuality="weak",
        missingPoints=missing_terms,
    )
    latest.answerQuality = "weak"
    return None, evaluation, None
