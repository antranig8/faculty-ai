import re

from app.models.response_models import PreparedQuestion
from app.services.cooldown import _normalize_message


GENERIC_LISTEN_TERMS = {
    "a",
    "an",
    "and",
    "app",
    "application",
    "concept",
    "customer",
    "data",
    "design",
    "good",
    "idea",
    "industry",
    "interview",
    "project",
    "solution",
    "student",
    "students",
    "system",
    "team",
    "user",
    "users",
}


def quoted_question_phrases(question_text: str) -> list[str]:
    phrases: list[str] = []
    for match in re.findall(r"['\"]([^'\"]{4,})['\"]", question_text):
        normalized = _normalize_message(match)
        if normalized and normalized not in phrases:
            phrases.append(normalized)
    return phrases


def _phrase_matches(normalized_text: str, phrase: str) -> bool:
    if phrase in normalized_text:
        return True

    words = [word for word in phrase.split() if word]
    if len(words) <= 1:
        return False

    # Deepgram may split or rephrase short quoted concepts. Require all words for
    # a two-word concept, or most words for longer quoted phrases.
    hit_count = sum(1 for word in words if word in normalized_text)
    required_hits = len(words) if len(words) <= 2 else max(2, len(words) - 1)
    return hit_count >= required_hits


def meaningful_listen_terms(question: PreparedQuestion) -> list[str]:
    terms: list[str] = []
    for term in question.listenFor:
        normalized = _normalize_message(term)
        if not normalized or normalized in GENERIC_LISTEN_TERMS:
            continue
        if len(normalized) < 4 and " " not in normalized:
            continue
        if normalized not in terms:
            terms.append(normalized)
    return terms


def prepared_question_is_topically_ready(question: PreparedQuestion, transcript_text: str) -> bool:
    normalized_text = _normalize_message(transcript_text)
    if not normalized_text:
        return False

    quoted_phrases = quoted_question_phrases(question.question)
    if quoted_phrases and not any(_phrase_matches(normalized_text, phrase) for phrase in quoted_phrases):
        return False

    listen_terms = meaningful_listen_terms(question)
    if not listen_terms:
        return bool(quoted_phrases)

    required_hits = 1 if quoted_phrases else min(2, len(listen_terms))
    hit_count = sum(1 for term in listen_terms if term in normalized_text)
    return hit_count >= required_hits


def prepared_question_is_answered(question: PreparedQuestion, transcript_text: str) -> bool:
    normalized_text = _normalize_message(transcript_text)
    if not normalized_text:
        return False
    return any(_normalize_message(marker) in normalized_text for marker in question.missingIfAbsent if marker.strip())
