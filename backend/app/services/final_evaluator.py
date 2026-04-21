import json
from datetime import timezone

from app.config import get_settings
from app.models.response_models import FinalEvaluation, FeedbackItem, ProfessorConfig, RubricScore
from app.services.cooldown import utc_now
from app.services.groq_client import build_groq_client, groq_reasoning_effort
from app.services.llm_errors import classify_llm_error, log_llm_exception
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


def _grade_from_numeric(numeric: int) -> str:
    if numeric >= 93:
        return "A"
    if numeric >= 90:
        return "A-"
    if numeric >= 87:
        return "B+"
    if numeric >= 83:
        return "B"
    if numeric >= 80:
        return "B-"
    if numeric >= 77:
        return "C+"
    if numeric >= 73:
        return "C"
    return "C-"


def _score_to_numeric(score: float) -> int:
    # Intro-course calibration: 3/5 should still land near a B-/C+ boundary, not an F-style score.
    return round(68 + (score / 5.0) * 28)


def _normalize_rubric_scores(config: ProfessorConfig, rubric_scores: list[RubricScore]) -> list[RubricScore]:
    wanted = [criterion for criterion in config.rubric]
    by_name = {item.criterion.strip().lower(): item for item in rubric_scores}
    normalized: list[RubricScore] = []
    for criterion in wanted:
        existing = by_name.get(criterion.strip().lower())
        if existing is None:
            normalized.append(
                RubricScore(
                    criterion=criterion,
                    score=3,
                    justification="Defaulted to a mid-range score because no criterion-specific evidence was returned.",
                )
            )
            continue

        normalized.append(
            RubricScore(
                criterion=criterion,
                score=max(2, min(5, int(existing.score))),
                justification=existing.justification.strip() or "Calibrated from the presentation transcript and live questioning.",
            )
        )
    return normalized


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
            score=max(3, min(5, 5 - len([item for item in feedback if criterion.lower() in item.reason.lower()]))),
            justification="Estimated from live feedback patterns during the presentation.",
        )
        for criterion in config.rubric
    ]
    avg_score = sum(item.score for item in rubric_scores) / max(1, len(rubric_scores))
    numeric = max(numeric, _score_to_numeric(avg_score))
    grade = _grade_from_numeric(numeric)

    return FinalEvaluation(
        sessionId=session_id,
        projectTitle=project_title,
        courseName=config.courseName,
        overallGrade=grade,
        numericScore=numeric,
        summary="Automatic fallback evaluation calibrated for an introductory engineering-professions presentation.",
        strongestPoints=["Presentation completed with a coherent live walkthrough."],
        biggestQuestions=biggest_questions or ["No major faculty concerns were recorded."],
        rubricScores=rubric_scores,
        createdAt=_created_at(),
    )


def _prompt(config: ProfessorConfig, project_title: str, transcript: list[str], feedback: list[FeedbackItem]) -> str:
    prompt_header = load_prompt(
        "final_evaluation.md",
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
        try:
            client = build_groq_client(settings.groq_api_key)
            completion = client.chat.completions.create(
                model=settings.faculty_ai_llm_model,
                messages=[{"role": "user", "content": _prompt(config, project_title, transcript, feedback)}],
                temperature=0.2,
                max_completion_tokens=1400,
                top_p=1,
                reasoning_effort=groq_reasoning_effort(settings.faculty_ai_llm_model),
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
                    normalized_scores = _normalize_rubric_scores(config, rubric_scores)
                    average_score = sum(item.score for item in normalized_scores) / max(1, len(normalized_scores))
                    numeric_score = _score_to_numeric(average_score)
                    return FinalEvaluation(
                        sessionId=session_id,
                        projectTitle=project_title,
                        courseName=config.courseName,
                        overallGrade=_grade_from_numeric(numeric_score),
                        numericScore=numeric_score,
                        summary=str(parsed.get("summary", "")).strip(),
                        strongestPoints=[str(item).strip() for item in parsed.get("strongestPoints", []) if str(item).strip()][:4],
                        biggestQuestions=[str(item).strip() for item in parsed.get("biggestQuestions", []) if str(item).strip()][:4],
                        rubricScores=normalized_scores,
                        createdAt=_created_at(),
                    )
        except Exception as exc:
            log_llm_exception("evaluate_presentation", exc)
            feedback = [
                *feedback,
                FeedbackItem(
                    type="clarification",
                    priority="low",
                    section="unknown",
                    message="Final evaluation fell back to rubric heuristics.",
                    reason=f"LLM final evaluation failed: {classify_llm_error(exc)}",
                    createdAt=_created_at(),
                ),
            ]

    return _fallback_evaluation(session_id, project_title, config, transcript, feedback)
