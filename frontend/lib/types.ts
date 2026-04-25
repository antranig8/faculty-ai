export type ProjectContext = {
  title: string;
  summary: string;
  stack: string[];
  goals: string[];
  rubric: string[];
  notes?: string;
};

export type FeedbackType = "question" | "critique" | "suggestion" | "clarification" | "praise";

export type FeedbackItem = {
  type: FeedbackType;
  priority: "low" | "medium" | "high";
  section:
    | "introduction"
    | "problem"
    | "solution"
    | "architecture"
    | "demo"
    | "evaluation"
    | "future_work"
    | "conclusion"
    | "unknown";
  message: string;
  reason: string;
  createdAt: string;
  slideNumber?: number | null;
  resolved?: boolean;
  resolvedAt?: string | null;
  resolutionReason?: string | null;
  sourceQuestionId?: string | null;
  autoResolutionTerms?: string[];
};

export type Slide = {
  slideNumber: number;
  title: string;
  content: string;
};

export type PreparedQuestion = {
  id: string;
  slideNumber: number;
  rubricCategory: string;
  type: FeedbackType;
  priority: "low" | "medium" | "high";
  question: string;
  listenFor: string[];
  missingIfAbsent: string[];
};

export type PresentationPreparation = {
  slides: Slide[];
  preparedQuestions: PreparedQuestion[];
  questionSource: "llm" | "heuristic";
  cacheHit: boolean;
};

export type ProfessorConfig = {
  courseName: string;
  assignmentName: string;
  rubric: string[];
  questionStyle: string;
  assignmentContext: string;
};

export type AnalyzeResponse = {
  trigger: boolean;
  feedback?: FeedbackItem;
  resolvedFeedback?: FeedbackItem;
  reason?: string;
  inferredCurrentSlide?: Slide;
};

export type SpeechProvider = "deepgram" | "assemblyai";

export type SpeechSession = {
  provider: SpeechProvider;
  accessToken?: string;
  expiresIn?: number;
  websocketUrl?: string;
  model?: string;
  language?: string;
};

export type TtsProvider = "browser" | "deepgram";

export type TtsPreviewResponse = {
  provider: "deepgram";
  configured: boolean;
  enabled: boolean;
  model: string;
  status: "scaffolded_not_implemented" | "enabled";
};
