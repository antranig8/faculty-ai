from dataclasses import asdict, dataclass
from datetime import timezone
from typing import Optional

from app.models.response_models import PreparedQuestion
from app.models.response_models import FeedbackItem
from app.models.response_models import Slide
from app.services.cooldown import utc_now
from app.services.question_matching import meaningful_listen_terms, prepared_question_is_topically_ready
from app.services.section_tracker import infer_section
from app.services.student_profiles import profile_hint
from app.services.transcript_evidence import TranscriptEvidence, extract_transcript_evidence

VAGUE_TERMS = ["better", "efficient", "improve", "personalized", "adaptive", "smart", "easy"]
CLAIM_TERMS = ["increase", "decrease", "faster", "more accurate", "better", "improve", "optimize"]
TECH_TERMS = ["react", "next", "fastapi", "python", "api", "database", "supabase", "model", "llm"]
SLIDE_HANDOFF_TERMS = [
    "any questions",
    "questions",
    "does anyone have questions",
    "do you have questions",
    "are there any questions",
    "that's it",
    "that is it",
]


@dataclass
class CandidateDiagnostic:
    interactionType: str
    score: int
    priority: str
    message: str
    reason: str
    sourceQuestionId: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _mentions_metric(text: str) -> bool:
    metric_markers = ["%", "percent", "metric", "measured", "evaluated", "tested", "survey", "baseline"]
    return _contains_any(text, metric_markers)


def _question_matches_transcript(question: PreparedQuestion, text: str) -> bool:
    return prepared_question_is_topically_ready(question, text)


def _concern_is_unanswered(question: PreparedQuestion, recent_text: str) -> bool:
    lower_recent = recent_text.lower()
    return not any(marker.lower() in lower_recent for marker in question.missingIfAbsent)


def _question_is_proactively_ready(
    question: PreparedQuestion,
    recent_text: str,
    recent_transcript: list[str],
    current_slide: Slide | None = None,
) -> bool:
    if question.priority == "low":
        return False

    normalized_recent = recent_text.lower()
    listen_terms = meaningful_listen_terms(question)
    slide_category = current_slide.slideCategory if current_slide else "unknown"

    if slide_category == "team_takeaway":
        # On the shared takeaway slide, avoid interrupting while the team is
        # still listing themes. Wait until they start defending priorities,
        # comparisons, disagreement, or some other team-level reasoning.
        reasoning_markers = [
            "why",
            "difference",
            "disagree",
            "priority",
            "prioritize",
            "tradeoff",
            "compared",
            "changed",
            "shaped",
        ]
        has_reasoning = any(marker in normalized_recent for marker in reasoning_markers)
        if len(recent_transcript) < 3 or not has_reasoning:
            return False

    if any(term in normalized_recent for term in listen_terms):
        return True

    # Prepared concerns are already scoped to the inferred slide. After enough
    # speech on that slide, surface the strongest missing concern before the
    # presenter explicitly asks for questions.
    word_count = len(recent_text.split())
    if question.priority == "high":
        return word_count >= 18
    return question.priority == "medium" and word_count >= 32


def _team_takeaway_ready_for_interrupt(current_text: str, current_slide: Slide | None) -> bool:
    if not current_slide or current_slide.slideCategory != "team_takeaway":
        return True

    normalized_recent = current_text.lower()
    reasoning_markers = [
        "why",
        "difference",
        "disagree",
        "priority",
        "prioritize",
        "tradeoff",
        "compared",
        "changed",
        "shaped",
    ]
    return any(marker in normalized_recent for marker in reasoning_markers)


def _cip_team_ready_for_interrupt(current_text: str, current_slide: Slide | None) -> bool:
    if not current_slide or current_slide.slideCategory != "cip_team_feedback":
        return True

    normalized_recent = current_text.lower()
    # When the team is already naming weaknesses and improvements, holding the
    # interruption often produces a better end-of-slide or closing question.
    self_critique_markers = [
        "we could improve",
        "more balanced",
        "cutting down text",
        "speaking guides",
        "equally developed",
        "improve the visual design",
    ]
    return not any(marker in normalized_recent for marker in self_critique_markers)


def _created_at() -> str:
    return utc_now().astimezone(timezone.utc).isoformat()


def _priority_rank(priority: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(priority, 0)


def is_slide_handoff(text: str) -> bool:
    lower_text = text.lower()
    return any(term in lower_text for term in SLIDE_HANDOFF_TERMS)


def _feedback_from_prepared_question(question: PreparedQuestion, section: str, reason: str) -> FeedbackItem:
    target_student = None
    if question.question and "," in question.question:
        possible_name = question.question.split(",", 1)[0].strip()
        if possible_name and all(part[:1].isupper() for part in possible_name.split() if part):
            target_student = possible_name
    return FeedbackItem(
        type=question.type,
        priority=question.priority,
        section=section,
        message=question.question,
        reason=f"Rubric focus: {question.rubricCategory}. {reason}",
        createdAt=_created_at(),
        slideNumber=question.slideNumber,
        sourceQuestionId=question.id,
        autoResolutionTerms=question.missingIfAbsent[:8],
        targetStudent=target_student,
    )


def _addressed_question(current_slide: Slide | None, default_message: str) -> str:
    # Keep fallback heuristics aligned with prepared-question targeting so
    # individual Assignment 6 slides can address the owning student directly.
    if not current_slide or current_slide.slideCategory != "individual_lesson" or not current_slide.slideAuthor:
        return default_message

    lowered = default_message[:1].lower() + default_message[1:] if default_message else default_message
    return f"{current_slide.slideAuthor}, {lowered}"


def _profile_major_prefix(current_slide: Slide | None, student_profiles) -> str | None:
    if not current_slide or not current_slide.slideAuthor:
        return None
    hint = profile_hint(student_profiles or {}, current_slide.slideAuthor)
    if not hint:
        return None
    return f"{current_slide.slideAuthor}, as a {hint}, "


def _question_rank(
    question: PreparedQuestion,
    recent_text: str,
    evidence: TranscriptEvidence,
    *,
    handoff_mode: bool = False,
) -> tuple[int, list[str], list[str]]:
    # Rank multiple valid prepared concerns so the deterministic path can pick
    # the strongest unresolved question on a slide instead of the first match.
    lower_recent = recent_text.lower()
    heard_terms = [term for term in question.listenFor if term.lower() in lower_recent]
    heard_terms.extend([item for item in evidence.evidenceMarkers if item not in heard_terms][:2])
    still_missing = [term for term in question.missingIfAbsent if term.lower() not in lower_recent]
    still_missing.extend([item for item in evidence.unansweredGaps if item not in still_missing][:2])
    already_covered = [term for term in question.missingIfAbsent if term.lower() in lower_recent]

    score = (_priority_rank(question.priority) * 4) + (len(heard_terms) * 3) + len(still_missing) - (len(already_covered) * 2)
    if prepared_question_is_topically_ready(question, recent_text):
        score += 2
    if handoff_mode:
        score += 1
    return score, heard_terms[:4], still_missing[:4]


def _freeform_candidates(
    text: str,
    project_title: str = "",
    current_slide: Slide | None = None,
    student_profiles=None,
) -> list[tuple[int, FeedbackItem, str]]:
    words = text.split()
    if len(words) < 12:
        return []

    lower_text = text.lower()
    section = infer_section(text)
    title = project_title.strip() or "this project"
    slide_category = current_slide.slideCategory if current_slide else "unknown"
    candidates: list[tuple[int, FeedbackItem, str]] = []
    profile_prefix = _profile_major_prefix(current_slide, student_profiles)

    if _contains_any(lower_text, ["takeaway", "takeaways"]) and not _contains_any(lower_text, ["perspective", "because", "we chose", "our group", "most important"]):
        candidates.append((
            18,
            FeedbackItem(
                type="question",
                priority="high",
                section=section,
                message="Where did your team disagree about the most important ENES 104 takeaway, and how did that disagreement shape this slide?",
                reason="The presenter discussed takeaways but has not yet distinguished team perspective from summary.",
                createdAt=_created_at(),
            ),
            "Generated Assignment 6 feedback for team perspective.",
        ))

    if (
        slide_category == "individual_lesson"
        or (
            slide_category == "unknown"
            and _contains_any(lower_text, ["lesson", "lessons", "learned", "workshop", "speaker"])
        )
    ) and not _contains_any(lower_text, ["apply", "future", "career", "use this", "engineering practice"]):
        candidates.append((
            19,
            FeedbackItem(
                type="question",
                priority="high",
                section=section,
                message=_addressed_question(
                    current_slide,
                    "What changed in your view of engineering because of this lesson, and what specific experience caused that change?",
                ),
                reason="The presenter mentioned a lesson but has not yet connected it to individual application.",
                createdAt=_created_at(),
                targetStudent=current_slide.slideAuthor if current_slide and current_slide.slideCategory == "individual_lesson" else None,
            ),
            "Generated Assignment 6 feedback for individual application.",
        ))

    if slide_category == "individual_lesson" and "good enough" in lower_text:
        candidates.append((
            22,
            FeedbackItem(
                type="question",
                priority="high",
                section=section,
                message=(
                    f"{profile_prefix}can you give one example of how 'good enough' in industry is different from doing low-quality work?"
                    if profile_prefix
                    else _addressed_question(
                        current_slide,
                        "can you give one example of how 'good enough' in industry is different from doing low-quality work?",
                    )
                ),
                reason="The presenter introduced 'good enough' as a key lesson, but that concept is easy to misunderstand without a concrete distinction.",
                createdAt=_created_at(),
                targetStudent=current_slide.slideAuthor if current_slide and current_slide.slideCategory == "individual_lesson" else None,
            ),
            "Generated Assignment 6 feedback for clarifying the 'good enough' concept.",
        ))

    if slide_category == "individual_lesson" and _contains_any(lower_text, ["impact", "failure", "reliable", "reliability", "opportunity", "opportunities"]):
        candidates.append((
            18,
            FeedbackItem(
                type="question",
                priority="high",
                section=section,
                message=(
                    f"{profile_prefix}how does this lesson change the way you would approach a future engineering project or team decision?"
                    if profile_prefix
                    else _addressed_question(
                        current_slide,
                        "how does this lesson change the way you would approach a future engineering project or team decision?",
                    )
                ),
                reason="The presenter named an important lesson, but the practical application to future engineering judgment is still unclear.",
                createdAt=_created_at(),
                targetStudent=current_slide.slideAuthor if current_slide and current_slide.slideCategory == "individual_lesson" else None,
            ),
            "Generated Assignment 6 feedback for future engineering application.",
        ))

    if (
        slide_category != "cip_team_feedback"
        and _contains_any(lower_text, ["cip", "continuous improvement", "what worked", "improve"])
        and not _contains_any(lower_text, ["management", "priority", "because", "specific"])
    ):
        candidates.append((
            17,
            FeedbackItem(
                type="question",
                priority="high",
                section=section,
                message="If management could only act on one improvement, which one would most change the next ENES 104 student's experience?",
                reason="The presenter discussed continuous improvement without a clear priority or rationale.",
                createdAt=_created_at(),
            ),
            "Generated Assignment 6 feedback for course improvement planning.",
        ))

    if slide_category == "cip_course_feedback" and _contains_any(lower_text, ["professionalism", "expectation", "expectations", "organized", "structure"]):
        candidates.append((
            22,
            FeedbackItem(
                type="question",
                priority="high",
                section=section,
                message="What specific professionalism expectation would you add to the first few ENES 104 sessions, and why that one first?",
                reason="The presenter proposed clearer professionalism expectations, but the recommendation still needs one concrete, prioritized change.",
                createdAt=_created_at(),
            ),
            "Generated Assignment 6 feedback for a more actionable CIP-1 recommendation.",
        ))

    if slide_category == "cip_team_feedback" and _contains_any(lower_text, ["team-building", "team building", "feedback", "contribute", "collaboration"]):
        candidates.append((
            20,
            FeedbackItem(
                type="question",
                priority="high",
                section=section,
                message="What is one piece of teammate feedback that actually changed the final presentation, and why did you accept it?",
                reason="The presenter described team coordination, but the specific feedback exchange and its impact on the final output are still missing.",
                createdAt=_created_at(),
            ),
            "Generated Assignment 6 feedback for concrete CIP-2 team feedback.",
        ))

    if slide_category == "cip_team_feedback" and _contains_any(lower_text, ["overall", "future engineering projects", "future projects", "keep learning", "every opportunity"]):
        candidates.append((
            19,
            FeedbackItem(
                type="question",
                priority="high",
                section=section,
                message="What is the single most important lesson your group would carry into future engineering projects?",
                reason="The presentation is moving into a closing synthesis, which is a good moment for one final forward-looking faculty question.",
                createdAt=_created_at(),
            ),
            "Generated Assignment 6 feedback for closing synthesis.",
        ))

    if _contains_any(lower_text, ["teamwork", "team work", "team building", "team-building", "feedback"]) and not _contains_any(lower_text, ["changed", "improved", "specific", "each other", "how"]):
        candidates.append((
            17,
            FeedbackItem(
                type="question",
                priority="high",
                section=section,
                message="What is one piece of teammate feedback that actually changed the final presentation, and why did you accept it?",
                reason="The presenter referenced teamwork or feedback without explaining the exchange and impact.",
                createdAt=_created_at(),
            ),
            "Generated Assignment 6 feedback for team feedback.",
        ))

    if _contains_any(lower_text, CLAIM_TERMS) and not _mentions_metric(lower_text):
        candidates.append((
            12,
            FeedbackItem(
                type="question",
                priority="medium",
                section=section,
                message=f"What metric supports the claim you just made about {title}?",
                reason="The presenter made an improvement or performance claim without evidence.",
                createdAt=_created_at(),
            ),
            "Generated feedback for an unsupported claim.",
        ))

    if _contains_any(lower_text, TECH_TERMS) and not _contains_any(lower_text, ["because", "chosen", "tradeoff", "alternative", "instead"]):
        candidates.append((
            11,
            FeedbackItem(
                type="critique",
                priority="medium",
                section=section,
                message="The stack is named, but the reason for choosing it over alternatives is still missing.",
                reason="A technical choice was mentioned without a clear justification.",
                createdAt=_created_at(),
            ),
            "Generated feedback for an unjustified technical choice.",
        ))

    if _contains_any(lower_text, ["personalized", "adaptive", "custom", "tailored"]):
        candidates.append((
            10,
            FeedbackItem(
                type="clarification",
                priority="medium",
                section=section,
                message="What exactly changes for each user, and what input controls that change?",
                reason="Personalization was mentioned but the mechanism is not yet specific.",
                createdAt=_created_at(),
            ),
            "Generated feedback for vague personalization.",
        ))

    if section == "problem" and _contains_any(lower_text, ["users", "students", "people"]) and not _contains_any(lower_text, ["interview", "survey", "observed", "evidence"]):
        candidates.append((
            10,
            FeedbackItem(
                type="question",
                priority="medium",
                section=section,
                message="What evidence shows this is a real problem for your target users?",
                reason="The problem is described, but the source of evidence is unclear.",
                createdAt=_created_at(),
            ),
            "Generated feedback for problem validation.",
        ))

    if _contains_any(lower_text, VAGUE_TERMS):
        candidates.append((
            6,
            FeedbackItem(
                type="suggestion",
                priority="low",
                section=section,
                message="Replace the broad claim with one concrete example or measurable outcome.",
                reason="The chunk uses broad language that would be stronger with a specific example.",
                createdAt=_created_at(),
            ),
            "Generated feedback for vague language.",
        ))

    return candidates


def diagnose_prepared_candidates(
    text: str,
    recent_transcript: list[str],
    prepared_questions: list[PreparedQuestion],
    current_slide_number: int | None,
    current_slide: Slide | None = None,
) -> list[CandidateDiagnostic]:
    relevant_questions = [
        question
        for question in prepared_questions
        if current_slide_number is None or question.slideNumber == current_slide_number
    ]
    recent_text = " ".join([*recent_transcript[-4:], text])
    evidence = extract_transcript_evidence(recent_transcript, text)
    diagnostics: list[CandidateDiagnostic] = []

    if not _team_takeaway_ready_for_interrupt(text, current_slide):
        return diagnostics
    if not _cip_team_ready_for_interrupt(text, current_slide):
        return diagnostics

    for question in relevant_questions:
        if question.priority == "low" and len(recent_transcript) < 2:
            continue
        if not _question_matches_transcript(question, recent_text):
            if not _question_is_proactively_ready(question, recent_text, recent_transcript, current_slide):
                continue
        if not _concern_is_unanswered(question, recent_text):
            continue

        score, _, _ = _question_rank(question, recent_text, evidence)
        diagnostics.append(
            CandidateDiagnostic(
                interactionType="prepared_question",
                score=score,
                priority=question.priority,
                message=question.question,
                reason=f"Prepared concern from rubric category '{question.rubricCategory}'.",
                sourceQuestionId=question.id,
            )
        )

    diagnostics.sort(key=lambda item: item.score, reverse=True)
    return diagnostics


def diagnose_freeform_candidates(
    text: str,
    project_title: str = "",
    current_slide: Slide | None = None,
    student_profiles=None,
) -> list[CandidateDiagnostic]:
    diagnostics = [
        CandidateDiagnostic(
            interactionType="freeform_question",
            score=score,
            priority=feedback.priority,
            message=feedback.message,
            reason=reason,
            sourceQuestionId=feedback.sourceQuestionId,
        )
        for score, feedback, reason in _freeform_candidates(
            text,
            project_title=project_title,
            current_slide=current_slide,
            student_profiles=student_profiles,
        )
    ]
    diagnostics.sort(key=lambda item: item.score, reverse=True)
    return diagnostics


def generate_slide_handoff_feedback(
    text: str,
    recent_transcript: list[str],
    prepared_questions: list[PreparedQuestion],
    current_slide_number: int | None,
    asked_question_ids: list[str],
    current_slide: Slide | None = None,
    project_title: str = "",
    student_profiles=None,
) -> tuple[Optional[FeedbackItem], str]:
    if not is_slide_handoff(text):
        return None, "No end-of-slide question handoff detected."

    relevant_questions = [
        question
        for question in prepared_questions
        if (current_slide_number is None or question.slideNumber == current_slide_number)
        and question.id not in asked_question_ids
    ]
    if not relevant_questions:
        return None, "No unasked prepared concern exists for this slide."

    recent_text = " ".join([*recent_transcript[-4:], text])
    section = infer_section(recent_text)
    evidence = extract_transcript_evidence(recent_transcript, text)
    ranked: list[tuple[int, PreparedQuestion]] = []
    for question in relevant_questions:
        if not _concern_is_unanswered(question, recent_text):
            continue
        score, _, _ = _question_rank(question, recent_text, evidence, handoff_mode=True)
        ranked.append((score, question))

    prepared_candidate = None
    prepared_score = None
    if ranked:
        ranked.sort(key=lambda item: item[0], reverse=True)
        prepared_score, question = ranked[0]
        prepared_candidate = _feedback_from_prepared_question(
            question=question,
            section=section,
            reason="The presenter invited questions at the end of the slide, so FacultyAI surfaced the strongest unasked prepared concern.",
        )

    freeform_ranked = _freeform_candidates(
        text,
        project_title=project_title,
        current_slide=current_slide,
        student_profiles=student_profiles,
    )
    freeform_candidate = None
    freeform_score = None
    freeform_reason = None
    if freeform_ranked:
        freeform_score, freeform_candidate, freeform_reason = sorted(freeform_ranked, key=lambda item: item[0], reverse=True)[0]

    if prepared_candidate is None and freeform_candidate is None:
        return None, "Prepared concerns for this slide were already addressed before the question handoff."

    if prepared_candidate is None:
        return freeform_candidate, f"{freeform_reason} Selected freeform faculty move at slide handoff."

    if freeform_candidate is None:
        return prepared_candidate, "Generated end-of-slide faculty question from prepared concerns."

    if current_slide and current_slide.slideCategory == "cip_course_feedback":
        if "professionalism expectation" in freeform_candidate.message.lower():
            freeform_score += 6
        if "metric" in prepared_candidate.message.lower() or "benchmark" in prepared_candidate.message.lower():
            prepared_score -= 2

    if current_slide and current_slide.slideCategory == "cip_team_feedback":
        if "single most important lesson" in freeform_candidate.message.lower():
            freeform_score += 4

    if prepared_score >= freeform_score + 1:
        return prepared_candidate, "Generated end-of-slide faculty question from prepared concerns."

    return freeform_candidate, f"{freeform_reason} Selected freeform faculty move at slide handoff."


def generate_candidate_feedback(
    text: str,
    project_title: str = "",
    current_slide: Slide | None = None,
    student_profiles=None,
) -> tuple[Optional[FeedbackItem], str]:
    candidates = _freeform_candidates(
        text,
        project_title=project_title,
        current_slide=current_slide,
        student_profiles=student_profiles,
    )
    if not candidates:
        return None, "No high-value freeform faculty move was found."
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, feedback, reason = candidates[0]
    return feedback, reason


def generate_slide_aware_feedback(
    text: str,
    recent_transcript: list[str],
    prepared_questions: list[PreparedQuestion],
    current_slide_number: int | None,
    current_slide: Slide | None = None,
) -> tuple[Optional[FeedbackItem], str]:
    words = text.split()
    if len(words) < 8:
        return None, "Transcript chunk is too short for slide-aware feedback."

    relevant_questions = [
        question
        for question in prepared_questions
        if current_slide_number is None or question.slideNumber == current_slide_number
    ]
    recent_text = " ".join([*recent_transcript[-4:], text])
    section = infer_section(recent_text)
    evidence = extract_transcript_evidence(recent_transcript, text)
    ranked: list[tuple[int, PreparedQuestion]] = []

    if not _team_takeaway_ready_for_interrupt(text, current_slide):
        return None, "Team takeaway slide is still in framing mode, so FacultyAI is waiting for stronger reasoning before interrupting."
    if not _cip_team_ready_for_interrupt(text, current_slide):
        return None, "CIP team-feedback slide is already in self-critique mode, so FacultyAI is holding for a better closing moment."

    for question in relevant_questions:
        if question.priority == "low" and len(recent_transcript) < 2:
            continue
        if not _question_matches_transcript(question, recent_text):
            if not _question_is_proactively_ready(question, recent_text, recent_transcript, current_slide):
                continue

        if not _concern_is_unanswered(question, recent_text):
            continue

        score, _, _ = _question_rank(question, recent_text, evidence)
        ranked.append((score, question))

    if ranked:
        ranked.sort(key=lambda item: item[0], reverse=True)
        question = ranked[0][1]
        return _feedback_from_prepared_question(
            question=question,
            section=section,
            reason="The current slide has enough spoken context for this prepared concern, but the explanation has not addressed it yet.",
        ), "Generated proactive feedback from prepared slide question."

    return None, "No prepared slide question matched an unanswered concern."


def generate_hybrid_feedback(
    text: str,
    recent_transcript: list[str],
    prepared_questions: list[PreparedQuestion],
    current_slide: Slide | None,
    project_title: str = "",
    student_profiles=None,
) -> tuple[Optional[FeedbackItem], str]:
    # The deterministic layer should also think in terms of the best faculty
    # move, not only the best prepared concern.
    prepared_candidate, prepared_reason = generate_slide_aware_feedback(
        text=text,
        recent_transcript=recent_transcript,
        prepared_questions=prepared_questions,
        current_slide_number=current_slide.slideNumber if current_slide else None,
        current_slide=current_slide,
    )
    freeform_candidate, freeform_reason = generate_candidate_feedback(
        text=text,
        project_title=project_title,
        current_slide=current_slide,
        student_profiles=student_profiles,
    )

    if prepared_candidate is None and freeform_candidate is None:
        return None, "No strong deterministic faculty move was found."
    if prepared_candidate is None:
        return freeform_candidate, f"{freeform_reason} Selected freeform faculty move."
    if freeform_candidate is None:
        return prepared_candidate, f"{prepared_reason} Selected prepared faculty move."

    prepared_score = (_priority_rank(prepared_candidate.priority) * 4) + 2
    freeform_score = _priority_rank(freeform_candidate.priority) * 4
    lower_text = text.lower()
    slide_category = current_slide.slideCategory if current_slide else "unknown"

    if slide_category == "individual_lesson":
        if "good enough" in lower_text and "good enough" in prepared_candidate.message.lower():
            prepared_score += 6
        if "what changed in your view of engineering" in freeform_candidate.message.lower() and _contains_any(
            lower_text,
            ["made me think differently", "future engineering", "career", "engineering practice", "changed how"],
        ):
            freeform_score -= 4

    if slide_category == "cip_course_feedback":
        if _contains_any(lower_text, ["professionalism", "expectation", "expectations", "organized", "structure"]):
            freeform_score += 5
            prepared_score += 1

    if slide_category == "cip_team_feedback":
        if "teammate feedback" in freeform_candidate.message.lower():
            freeform_score += 4
        if "future engineering projects" in freeform_candidate.message.lower():
            freeform_score += 3
        if "little collaboration" in prepared_candidate.message.lower():
            prepared_score += 4

    if prepared_score >= freeform_score + 1:
        return prepared_candidate, f"{prepared_reason} Selected prepared faculty move over freeform alternative."
    return freeform_candidate, f"{freeform_reason} Selected freeform faculty move over prepared alternative."


def diagnose_hybrid_candidates(
    text: str,
    recent_transcript: list[str],
    prepared_questions: list[PreparedQuestion],
    current_slide: Slide | None,
    project_title: str = "",
    student_profiles=None,
) -> dict:
    prepared = diagnose_prepared_candidates(
        text=text,
        recent_transcript=recent_transcript,
        prepared_questions=prepared_questions,
        current_slide_number=current_slide.slideNumber if current_slide else None,
        current_slide=current_slide,
    )
    freeform = diagnose_freeform_candidates(
        text=text,
        project_title=project_title,
        current_slide=current_slide,
        student_profiles=student_profiles,
    )

    selected = None
    prepared_top = prepared[0] if prepared else None
    freeform_top = freeform[0] if freeform else None
    if prepared_top and freeform_top:
        if prepared_top.score >= freeform_top.score + 1:
            selected = prepared_top
        else:
            selected = freeform_top
    else:
        selected = prepared_top or freeform_top

    return {
        "preparedCandidates": [item.to_dict() for item in prepared[:3]],
        "freeformCandidates": [item.to_dict() for item in freeform[:3]],
        "selectedCandidate": selected.to_dict() if selected else None,
    }
