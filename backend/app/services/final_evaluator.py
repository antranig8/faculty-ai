import json
from datetime import timezone

from groq import Groq

from app.config import get_settings
from app.models.response_models import FinalEvaluation, FeedbackItem, ProfessorConfig, RubricScore
from app.services.cooldown import utc_now
from app.services.prompt_loader import load_prompt
from app.services.rubric_loader import load_professor_config_from_template


def _created_at() -> str:
    return utc_now().astimezone(timezone.utc).isoformat()


def _heuristic_grade(feedback: list[FeedbackItem]) -> tuple[str, int]:
    penalty = 0
    for item in feedback:
        if item.priority == "high":
            penalty += 10
        elif item.priority == "medium":
            penalty += 6
        else:
            penalty += 2
    numeric = max(70, 96 - penalty)
    if numeric >= 93:
        return "A", numeric
    if numeric >= 90:
        return "A-", numeric
    if numeric >= 87:
        return "B+", numeric
    if numeric >= 83:
        return "B", numeric
    if numeric >= 80:
        return "B-", numeric
    if numeric >= 77:
        return "C+", numeric
    return "C", numeric


def _fallback_evaluation(session_id: str, project_title: str, config: ProfessorConfig, transcript: list[str], feedback: list[FeedbackItem]) -> FinalEvaluation:
    grade, numeric = _heuristic_grade(feedback)
    biggest_questions = []
    for item in reversed(feedback):
        if item.message not in biggest_questions:
            biggest_questions.append(item.message)
        if len(biggest_questions) == 3:
            break

    rubric_scores = [
        RubricScore(
            criterion=criterion,
            score=max(2, min(5, 5 - len([item for item in feedback if criterion.lower() in item.reason.lower()]))),
            justification="Estimated from live feedback patterns during the presentation.",
        )
        for criterion in config.rubric
    ]

    return FinalEvaluation(
        sessionId=session_id,
        projectTitle=project_title,
        courseName=config.courseName,
        overallGrade=grade,
        numericScore=numeric,
        summary="Automatic fallback evaluation based on transcript coverage and faculty feedback intensity.",
        strongestPoints=["Presentation completed with a coherent live walkthrough."],
        biggestQuestions=biggest_questions or ["No major faculty concerns were recorded."],
        rubricScores=rubric_scores,
        createdAt=_created_at(),
    )


def _prompt(config: ProfessorConfig, project_title: str, transcript: list[str], feedback: list[FeedbackItem]) -> str:
    prompt_header = load_prompt(
        "final_evaluation.txt",
        (
            "You are FacultyAI writing a final presentation evaluation.\n"
            "Use the professor rubric, transcript, and faculty feedback.\n"
            "Return strict JSON only."
        ),
    )
    return (
        f"{prompt_header}\n"
        f"Professor config: {config.model_dump_json()}\n"
        f"Project title: {json.dumps(project_title)}\n"
        f"Transcript excerpt: {json.dumps(transcript[-20:])}\n"
        f"Faculty feedback history: {json.dumps([item.model_dump(mode='json') for item in feedback[-10:]])}"
    )


def evaluate_presentation(session_id: str, project_title: str, transcript: list[str], feedback: list[FeedbackItem]) -> FinalEvaluation:
    config = load_professor_config_from_template() or ProfessorConfig()
    settings = get_settings()
    if settings.faculty_ai_llm_provider in {"groq", "openai"} and settings.groq_api_key:
        client = Groq(api_key=settings.groq_api_key)
        completion = client.chat.completions.create(
            model=settings.faculty_ai_llm_model,
            messages=[{"role": "user", "content": _prompt(config, project_title, transcript, feedback)}],
            temperature=0.2,
            max_completion_tokens=1400,
            top_p=1,
            reasoning_effort="medium",
            stream=True,
            stop=None,
        )

        parts: list[str] = []
        for chunk in completion:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                parts.append(delta)

        raw = "".join(parts).strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end >= start:
            parsed = json.loads(raw[start : end + 1])
            rubric_scores = [
                RubricScore(
                    criterion=item["criterion"],
                    score=int(item["score"]),
                    justification=str(item["justification"]).strip(),
                )
                for item in parsed.get("rubricScores", [])
            ]
            if rubric_scores:
                return FinalEvaluation(
                    sessionId=session_id,
                    projectTitle=project_title,
                    courseName=config.courseName,
                    overallGrade=str(parsed.get("overallGrade", "B")),
                    numericScore=int(parsed.get("numericScore", 85)),
                    summary=str(parsed.get("summary", "")).strip(),
                    strongestPoints=[str(item).strip() for item in parsed.get("strongestPoints", []) if str(item).strip()][:4],
                    biggestQuestions=[str(item).strip() for item in parsed.get("biggestQuestions", []) if str(item).strip()][:4],
                    rubricScores=rubric_scores,
                    createdAt=_created_at(),
                )

    return _fallback_evaluation(session_id, project_title, config, transcript, feedback)
