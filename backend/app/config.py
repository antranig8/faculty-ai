from dataclasses import dataclass
import os
from pathlib import Path


_ENV_LOADED = False


def _load_dotenv() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    current = Path(__file__).resolve()
    candidates = [
        Path.cwd() / ".env",
        current.parents[2] / ".env",
        current.parents[1] / ".env",
    ]

    for env_path in candidates:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    _ENV_LOADED = True


@dataclass(frozen=True)
class Settings:
    deepgram_api_key: str | None
    groq_api_key: str | None
    faculty_ai_app_api_key: str | None
    faculty_ai_allowed_origins: list[str]
    faculty_ai_speech_provider: str
    faculty_ai_llm_provider: str
    faculty_ai_llm_model: str
    faculty_ai_rephrase_model: str
    deepgram_model: str
    deepgram_language: str


def get_settings() -> Settings:
    _load_dotenv()
    allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "FACULTY_AI_ALLOWED_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]
    return Settings(
        deepgram_api_key=os.getenv("DEEPGRAM_API_KEY"),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        faculty_ai_app_api_key=os.getenv("FACULTY_AI_APP_API_KEY"),
        faculty_ai_allowed_origins=allowed_origins,
        faculty_ai_speech_provider=os.getenv("FACULTY_AI_SPEECH_PROVIDER", "deepgram"),
        faculty_ai_llm_provider=os.getenv("FACULTY_AI_LLM_PROVIDER", "heuristic"),
        faculty_ai_llm_model=os.getenv("FACULTY_AI_LLM_MODEL", "qwen/qwen3-32b"),
        faculty_ai_rephrase_model=os.getenv("FACULTY_AI_REPHRASE_MODEL", "qwen/qwen3-8b"),
        deepgram_model=os.getenv("DEEPGRAM_MODEL", "flux-general-en"),
        deepgram_language=os.getenv("DEEPGRAM_LANGUAGE", "en-US"),
    )
