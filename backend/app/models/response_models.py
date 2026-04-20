from typing import Literal, Optional

from pydantic import BaseModel, Field


FeedbackType = Literal["question", "critique", "suggestion", "clarification", "praise"]
Priority = Literal["low", "medium", "high"]
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


class SessionStartResponse(BaseModel):
    sessionId: str


class FeedbackItem(BaseModel):
    type: FeedbackType
    priority: Priority
    section: Section
    message: str
    reason: str
    createdAt: str


class Slide(BaseModel):
    slideNumber: int
    title: str
    content: str


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


class AnalyzeChunkResponse(BaseModel):
    trigger: bool
    feedback: Optional[FeedbackItem] = None
    reason: Optional[str] = None
