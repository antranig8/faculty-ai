from pathlib import Path
import re

from app.models.response_models import ProfessorConfig


_PROMPT_RUBRIC_PATH = Path(__file__).resolve().parents[1] / "prompts" / "professor_rubric_template.md"
_DOCS_RUBRIC_PATH = Path(__file__).resolve().parents[3] / "docs" / "professor_rubric_template.md"


def _extract_section(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def load_professor_config_from_template() -> ProfessorConfig | None:
    rubric_path = _PROMPT_RUBRIC_PATH if _PROMPT_RUBRIC_PATH.exists() else _DOCS_RUBRIC_PATH
    if not rubric_path.exists():
        return None

    text = rubric_path.read_text(encoding="utf-8")
    course_name = _extract_section(text, "Course").splitlines()[0].strip() if _extract_section(text, "Course") else "ENES 104"
    assignment_name = _extract_section(text, "Assignment").splitlines()[0].strip() if _extract_section(text, "Assignment") else "Project Presentation"
    rubric_section = _extract_section(text, "Rubric Criteria")
    rubric = [
        line.strip().lstrip("-").strip()
        for line in rubric_section.splitlines()
        if line.strip().startswith("-")
    ]
    question_style = _extract_section(text, "Question Style").splitlines()[0].strip() if _extract_section(text, "Question Style") else "skeptical but fair faculty examiner"
    guidance = _extract_section(text, "Guidance For FacultyAI")
    assignment_context = _extract_section(text, "Assignment Context")
    combined_context = "\n\n".join(part for part in [guidance, assignment_context] if part).strip()

    return ProfessorConfig(
        courseName=course_name or "ENES 104",
        assignmentName=assignment_name or "Project Presentation",
        rubric=rubric or ["clarity", "technical justification", "evidence", "evaluation", "feasibility"],
        questionStyle=question_style or "skeptical but fair faculty examiner",
        assignmentContext=combined_context,
    )
