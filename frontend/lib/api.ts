import type {
  AnalyzeResponse,
  FeedbackItem,
  PreparedQuestion,
  PresentationPreparation,
  ProfessorConfig,
  ProjectContext,
  SpeechProvider,
  SpeechSession,
  Slide,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_AUTH_KEY = process.env.NEXT_PUBLIC_FACULTY_AI_APP_API_KEY;

function buildHeaders(headers: HeadersInit = {}): HeadersInit {
  return API_AUTH_KEY
    ? {
        ...headers,
        "x-facultyai-key": API_AUTH_KEY,
      }
    : headers;
}

export function getSpeechProxyUrl(): string {
  const base = API_BASE.replace(/^http/, "ws");
  if (!API_AUTH_KEY) {
    return `${base}/speech/deepgram/proxy`;
  }

  const separator = base.includes("?") ? "&" : "?";
  return `${base}/speech/deepgram/proxy${separator}key=${encodeURIComponent(API_AUTH_KEY)}`;
}

export async function startSession(projectContext: ProjectContext): Promise<string> {
  const response = await fetch(`${API_BASE}/session/start`, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }),
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
    headers: buildHeaders({ "Content-Type": "application/json" }),
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
    headers: buildHeaders({ "Content-Type": "application/json" }),
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
    headers: buildHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => undefined);
    throw new Error(error?.detail ?? "Unable to upload presentation.");
  }

  return response.json();
}

export async function getProfessorConfig(): Promise<ProfessorConfig> {
  const response = await fetch(`${API_BASE}/professor/config`, {
    headers: buildHeaders(),
  });

  if (!response.ok) {
    throw new Error("Unable to load professor configuration.");
  }

  return response.json();
}

export async function saveProfessorConfig(config: ProfessorConfig): Promise<ProfessorConfig> {
  const response = await fetch(`${API_BASE}/professor/config`, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ config }),
  });

  if (!response.ok) {
    throw new Error("Unable to save professor configuration.");
  }

  return response.json();
}

export async function getFeedback(sessionId: string): Promise<FeedbackItem[]> {
  const response = await fetch(`${API_BASE}/session/${sessionId}/feedback`, {
    headers: buildHeaders(),
  });

  if (!response.ok) {
    throw new Error("Unable to load feedback history.");
  }

  return response.json();
}

export async function createSpeechSession(provider: SpeechProvider): Promise<SpeechSession> {
  const response = await fetch(`${API_BASE}/speech/${provider}/session`, {
    method: "POST",
    headers: buildHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => undefined);
    throw new Error(error?.detail ?? "Unable to start live speech.");
  }

  return response.json();
}
