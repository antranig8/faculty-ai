from pathlib import Path


_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt(name: str, fallback: str = "") -> str:
    prompt_path = _PROMPTS_DIR / name
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return fallback.strip()
