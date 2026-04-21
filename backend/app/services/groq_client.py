from groq import Groq


def build_groq_client(api_key: str) -> Groq:
    return Groq(api_key=api_key, max_retries=0)


def groq_reasoning_effort(model: str) -> str:
    lowered = model.lower()
    if lowered.startswith("qwen/") or "qwen" in lowered:
        return "default"
    return "medium"
