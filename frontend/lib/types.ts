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
  reason?: string;
};
