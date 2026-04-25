from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.response_models import PreparedQuestion, ProfessorConfig, Slide


class ProjectContext(BaseModel):
    title: str = Field(default="")
    summary: str = Field(default="")
    stack: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    rubric: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class SessionStartRequest(BaseModel):
    projectContext: ProjectContext


class AnalyzeChunkRequest(BaseModel):
    sessionId: str
    transcriptChunk: str
    recentTranscript: List[str] = Field(default_factory=list)
    recentFeedback: List[str] = Field(default_factory=list)
    projectContext: ProjectContext
    currentSlide: Optional[Slide] = None
    slideMode: Literal["auto", "manual"] = "auto"
    presentationSlides: List[Slide] = Field(default_factory=list)
    preparedQuestions: List[PreparedQuestion] = Field(default_factory=list)


class PresentationPrepareRequest(BaseModel):
    projectContext: ProjectContext
    slideOutline: str


class ProfessorConfigRequest(BaseModel):
    config: ProfessorConfig


class FeedbackResolutionRequest(BaseModel):
    resolved: bool = True
    resolutionReason: Optional[str] = None
    sourceQuestionId: Optional[str] = None
    message: Optional[str] = None


class TextToSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1200)
    provider: str = "deepgram"
