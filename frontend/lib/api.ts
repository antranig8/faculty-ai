import type {
  AnalyzeResponse,
  FeedbackItem,
  PreparedQuestion,
  PresentationPreparation,
  ProfessorConfig,
  ProjectContext,
  Slide,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function startSession(projectContext: ProjectContext): Promise<string> {
  const response = await fetch(`${API_BASE}/session/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ projectContext }),
  });

  if (!response.ok) {
    throw new Error("Unable to start presentation session.");
  }

  const data = (await response.json()) as { sessionId: string };
  return data.sessionId;
}

export async function analyzeChunk(params: {
  sessionId: string;
  transcriptChunk: string;
  recentTranscript: string[];
  recentFeedback: string[];
  projectContext: ProjectContext;
  currentSlide?: Slide;
  preparedQuestions?: PreparedQuestion[];
}): Promise<AnalyzeResponse> {
  const response = await fetch(`${API_BASE}/analyze-chunk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    throw new Error("Unable to analyze transcript chunk.");
  }

  return response.json();
}

export async function preparePresentation(params: {
  projectContext: ProjectContext;
  slideOutline: string;
}): Promise<PresentationPreparation> {
  const response = await fetch(`${API_BASE}/presentation/prepare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    throw new Error("Unable to prepare slide-aware questions.");
  }

  return response.json();
}

export async function uploadPresentation(file: File): Promise<PresentationPreparation> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/presentation/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => undefined);
    throw new Error(error?.detail ?? "Unable to upload presentation.");
  }

  return response.json();
}

export async function getProfessorConfig(): Promise<ProfessorConfig> {
  const response = await fetch(`${API_BASE}/professor/config`);

  if (!response.ok) {
    throw new Error("Unable to load professor configuration.");
  }

  return response.json();
}

export async function saveProfessorConfig(config: ProfessorConfig): Promise<ProfessorConfig> {
  const response = await fetch(`${API_BASE}/professor/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });

  if (!response.ok) {
    throw new Error("Unable to save professor configuration.");
  }

  return response.json();
}

export async function getFeedback(sessionId: string): Promise<FeedbackItem[]> {
  const response = await fetch(`${API_BASE}/session/${sessionId}/feedback`);

  if (!response.ok) {
    throw new Error("Unable to load feedback history.");
  }

  return response.json();
}
