import re

from app.config import get_settings
from app.services.groq_client import build_groq_client, groq_reasoning_effort

QUESTION_REPHRASE_MAX_COMPLETION_TOKENS = 45


def _clean_text(value: str) -> str:
    compact = " ".join(value.split()).strip()
    return compact.strip("\"' ")


def _extract_rephrased_question(value: str) -> str:
    without_thinking = re.sub(r"<think>.*?</think>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    compact = _clean_text(without_thinking)
    if not compact:
        return ""

    lines = [_clean_text(line) for line in re.split(r"[\r\n]+", without_thinking) if _clean_text(line)]
    question_lines = [line for line in lines if "?" in line]
    if question_lines:
        return question_lines[-1]

    sentences = [part.strip() for part in re.split(r"(?<=[?.!])\s+", compact) if part.strip()]
    if sentences:
        return sentences[-1]

    return compact


def rephrase_question(question: str) -> str | None:
    settings = get_settings()
    if not settings.groq_api_key:
        return None

    model = settings.faculty_ai_rephrase_model or settings.faculty_ai_llm_model

    clean_question = _clean_text(question)
    if not clean_question:
        return None

    client = build_groq_client(settings.groq_api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a question rewriter. "
                    "Your only job is to rewrite one question in simpler spoken English. "
                    "Keep the meaning the same. Make it shorter, plainer, and easier to understand. "
                    "Return exactly one rewritten question and nothing else. "
                    "Do not explain. Do not reason aloud. Do not use tags. Do not add notes or labels."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Rewrite this in simpler words for a student presenter.\n"
                    "Rules:\n"
                    "- Keep it to one sentence.\n"
                    "- Keep the same meaning.\n"
                    "- Use plain language.\n"
                    "- Output only the rewritten question.\n"
                    f"Question: {clean_question}"
                ),
            },
        ],
        temperature=0,
        max_completion_tokens=QUESTION_REPHRASE_MAX_COMPLETION_TOKENS,
        top_p=1,
        reasoning_effort=groq_reasoning_effort(model),
    )

    content = completion.choices[0].message.content if completion.choices else None
    if not content:
        return None

    rewritten = _extract_rephrased_question(content)
    return rewritten or None
