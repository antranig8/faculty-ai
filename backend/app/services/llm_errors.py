import logging
import traceback


logger = logging.getLogger("faculty_ai.llm")


def log_llm_exception(context: str, exc: Exception) -> None:
    logger.error("%s failed: %s\n%s", context, exc, traceback.format_exc())


def classify_llm_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    lower = message.lower()
    if "429" in lower or "rate limit" in lower or "too many requests" in lower:
        return f"{message} (likely provider rate limit)"
    return message
