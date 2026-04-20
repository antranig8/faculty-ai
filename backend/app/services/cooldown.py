from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Dict, List

MIN_SECONDS_BETWEEN_ALERTS = 15
MAX_ALERTS_PER_SESSION = 7


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def seconds_since(value: datetime | None) -> float:
    if value is None:
        return 10_000
    return (utc_now() - value).total_seconds()


def too_similar(message: str, existing_messages: List[str], threshold: float = 0.72) -> bool:
    normalized = message.lower().strip()
    for existing in existing_messages[-5:]:
        ratio = SequenceMatcher(None, normalized, existing.lower().strip()).ratio()
        if ratio >= threshold:
            return True
    return False


def can_emit_feedback(session: Dict, candidate_message: str) -> tuple[bool, str]:
    if len(session["feedback"]) >= MAX_ALERTS_PER_SESSION:
        return False, "Maximum feedback count reached for this session."

    elapsed = seconds_since(session.get("last_feedback_at"))
    if elapsed < MIN_SECONDS_BETWEEN_ALERTS:
        return False, f"Cooldown active. Wait {round(MIN_SECONDS_BETWEEN_ALERTS - elapsed)} more seconds."

    previous_messages = [item.message for item in session["feedback"]]
    if too_similar(candidate_message, previous_messages):
        return False, "Similar feedback was already shown recently."

    return True, "Feedback passed cooldown checks."

