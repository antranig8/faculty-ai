from typing import Literal, Optional

from pydantic import BaseModel, Field


FeedbackType = Literal["question", "critique", "suggestion", "clarification", "praise"]
Priority = Literal["low", "medium", "high"]
DeliveryStatus = Literal["queued", "active", "resolved"]
AnswerQuality = Literal["weak", "partial", "strong"]
Section = Literal[
    "introduction",
    "problem",
    "solution",
    "architecture",
    "demo",
    "evaluation",
    "future_work",
    "conclusion",
    "unknown",
]
SlideCategory = Literal[
    "title",
    "team_takeaway",
    "individual_lesson",
    "cip_course_feedback",
    "cip_team_feedback",
    "appendix",
    "unknown",
]


class SessionStartResponse(BaseModel):
    sessionId: str


class FeedbackItem(BaseModel):
    type: FeedbackType
    priority: Priority
    section: Section
    message: str
    reason: str
    createdAt: str
    slideNumber: Optional[int] = None
    resolved: bool = False
    resolvedAt: Optional[str] = None
    resolutionReason: Optional[str] = None
    sourceQuestionId: Optional[str] = None
    autoResolutionTerms: list[str] = Field(default_factory=list)
    deliveryStatus: DeliveryStatus = "active"
    followUpToQuestionId: Optional[str] = None
    answerQuality: Optional[AnswerQuality] = None
    targetStudent: Optional[str] = None


class Slide(BaseModel):
    slideNumber: int
    title: str
    content: str
    slideCategory: SlideCategory = "unknown"
    slideAuthor: Optional[str] = None


class PreparedQuestion(BaseModel):
    id: str
    slideNumber: int
    rubricCategory: str
    type: FeedbackType
    priority: Priority
    question: str
    listenFor: list[str]
    missingIfAbsent: list[str]


class PresentationPrepareResponse(BaseModel):
    slides: list[Slide]
    preparedQuestions: list[PreparedQuestion]
    questionSource: Literal["llm", "heuristic"]
    cacheHit: bool = False


class ProfessorConfig(BaseModel):
    courseName: str = "ENES 104"
    assignmentName: str = "Project Presentation"
    rubric: list[str] = Field(
        default_factory=lambda: [
            "clarity",
            "technical justification",
            "evidence",
            "evaluation",
            "feasibility",
        ]
    )
    questionStyle: str = "skeptical but fair faculty examiner"
    assignmentContext: str = ""


class AnswerEvaluation(BaseModel):
    questionId: str
    answered: bool
    answerQuality: AnswerQuality
    missingPoints: list[str] = Field(default_factory=list)
    shouldAskFollowUp: bool = False
    followUpQuestion: Optional[str] = None


class AnalyzeChunkResponse(BaseModel):
    trigger: bool
    feedback: Optional[FeedbackItem] = None
    queuedFeedback: Optional[FeedbackItem] = None
    resolvedFeedback: Optional[FeedbackItem] = None
    answerEvaluation: Optional[AnswerEvaluation] = None
    reason: Optional[str] = None
    inferredCurrentSlide: Optional[Slide] = None


class SpeechSessionResponse(BaseModel):
    provider: str
    accessToken: Optional[str] = None
    expiresIn: Optional[int] = None
    websocketUrl: Optional[str] = None
    model: Optional[str] = None
    language: Optional[str] = None


class QuestionRephraseResponse(BaseModel):
    rephrasedQuestion: str
