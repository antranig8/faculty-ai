from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import dotenv_values


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

        for key, value in dotenv_values(env_path, encoding="utf-8-sig", interpolate=False).items():
            if value is not None:
                os.environ.setdefault(key, value)

    _ENV_LOADED = True


@dataclass(frozen=True)
class Settings:
    deepgram_api_key: str | None
    groq_api_key: str | None
    faculty_ai_app_api_key: str | None
    faculty_ai_allowed_origins: list[str]
    faculty_ai_llm_provider: str
    faculty_ai_llm_model: str
    faculty_ai_rephrase_model: str
    deepgram_model: str
    deepgram_language: str
    faculty_ai_db_path: Path

    @property
    def uses_groq(self) -> bool:
        return self.faculty_ai_llm_provider in {"groq", "openai"} and bool(self.groq_api_key)


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
        faculty_ai_llm_provider=os.getenv("FACULTY_AI_LLM_PROVIDER", "heuristic"),
        faculty_ai_llm_model=os.getenv("FACULTY_AI_LLM_MODEL", "openai/gpt-oss-120b"),
        faculty_ai_rephrase_model=os.getenv("FACULTY_AI_REPHRASE_MODEL", "qwen/qwen3.8-27b"),
        deepgram_model=os.getenv("DEEPGRAM_MODEL", "flux-general-en"),
        deepgram_language=os.getenv("DEEPGRAM_LANGUAGE", "en-US"),
        faculty_ai_db_path=Path(os.getenv("FACULTY_AI_DB_PATH") or Path(__file__).resolve().parents[2] / "faculty_ai.db"),
    )
