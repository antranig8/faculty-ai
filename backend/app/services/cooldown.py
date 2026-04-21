from datetime import datetime, timezone
from difflib import SequenceMatcher
import re
from typing import Dict, List

MIN_SECONDS_BETWEEN_ALERTS = 25
MAX_ALERTS_PER_SESSION = 7


def _normalize_message(message: str) -> str:
    lowered = message.lower().strip()
    lowered = re.sub(r"[^a-z0-9\s]", "", lowered)
    return " ".join(lowered.split())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def seconds_since(value: datetime | None) -> float:
    if value is None:
        return 10_000
    return (utc_now() - value).total_seconds()


def too_similar(message: str, existing_messages: List[str], threshold: float = 0.72) -> bool:
    normalized = _normalize_message(message)
    for existing in existing_messages[-5:]:
        existing_normalized = _normalize_message(existing)
        if not existing_normalized:
            continue
        if normalized == existing_normalized:
            return True
        if normalized in existing_normalized or existing_normalized in normalized:
            return True
        ratio = SequenceMatcher(None, normalized, existing_normalized).ratio()
        if ratio >= 0.64:
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

