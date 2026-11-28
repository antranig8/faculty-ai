"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { FacultyAlert } from "@/components/FacultyAlert";
import { FeedbackDrawer } from "@/components/FeedbackDrawer";
import { PresentationUpload } from "@/components/PresentationUpload";
import { SessionControls } from "@/components/SessionControls";
import { SlideTracker } from "@/components/SlideTracker";
import { TranscriptPanel } from "@/components/TranscriptPanel";
import { analyzeChunk, getDeepgramTtsStreamUrl, getProfessorConfig, getSpeechProxyUrl, rephraseFacultyQuestion, startSession, synthesizeDeepgramSpeech, updateFeedbackResolution, uploadPresentation } from "@/lib/api";
import type { FeedbackItem, PreparedQuestion, ProfessorConfig, ProjectContext, Slide } from "@/lib/types";

const defaultProjectContext: ProjectContext = {
  title: "Project Presentation",
  summary: "",
  stack: [],
  goals: [],
  rubric: ["clarity", "technical justification", "evaluation"],
  notes: "",
};
const REPEAT_REQUEST_PATTERNS = [
  /\bcan you repeat that\b/i,
  /\bcould you repeat that\b/i,
  /\brepeat that\b/i,
  /\brepeat the question\b/i,
  /\bcan you say that again\b/i,
  /\bcould you say that again\b/i,
  /\bsay that again\b/i,
  /\bwhat was the question\b/i,
];
const QUESTION_REPHRASE_PATTERNS = [
  /\bi do not get the question\b/i,
  /\bi don't get the question\b/i,
  /\bi do not understand the question\b/i,
  /\bi don't understand the question\b/i,
  /\bcan you rephrase (?:that|the question)\b/i,
  /\bcould you rephrase (?:that|the question)\b/i,
  /\bcan you make (?:that|the question) simpler\b/i,
  /\bcould you make (?:that|the question) simpler\b/i,
  /\bwhat do you mean by that question\b/i,
];
const QUESTION_CONFIRMATION_PATTERNS = [
  /\bdoes that answer (?:your|the) question\b/i,
  /\bdid that answer (?:your|the) question\b/i,
  /\bdoes that answer it\b/i,
  /\bdid that answer it\b/i,
  /\bis that a good answer\b/i,
  /\bdoes that make sense\b/i,
];
const DEEPGRAM_TTS_SAMPLE_RATE = 48000;
const FACULTY_TTS_PLAYBACK_RATE = 1.0;
const FACULTY_TTS_OPENER = "I have a question.";
const FACULTY_TTS_REPHRASE_OPENER = "Let me rephrase that.";
const LIVE_MAX_TURN_WORDS = 55;
const LIVE_FORCED_CHUNK_MIN_NEW_WORDS = 18;
const FACULTY_ACKNOWLEDGMENT = "Yes, thank you.";
type SlideMode = "auto" | "manual";

function normalizeTextForSpeech(text: string) {
  return text.replace(/\bENES\b/g, "E N E S");
}

function normalizeQuestionForComparison(text: string) {
  return text.toLowerCase().replace(/[^a-z0-9\s]/g, "").replace(/\s+/g, " ").trim();
}

function simplifyQuestionText(message: string) {
  const compact = message.replace(/\s+/g, " ").trim();

  const exampleDifference = compact.match(/^([^,]+,\s+)?can you give one example of how (.+?) is different from (.+?)\?$/i);
  if (exampleDifference) {
    const [, prefix = "", left, right] = exampleDifference;
    return `${prefix}I mean: can you name one situation where ${left} is acceptable, but ${right} would be a problem?`;
  }

  const addMore = compact.match(/^([^,]+,\s+)?what specifically can you add about (.+?)\?$/i);
  if (addMore) {
    const [, prefix = "", topic] = addMore;
    return `${prefix}can you explain ${topic} a little more simply?`;
  }

  const futureChange = compact.match(/^([^,]+,\s+)?what concrete change will you make in your future engineering work because of that lesson\?$/i);
  if (futureChange) {
    const [, prefix = ""] = futureChange;
    return `${prefix}what is one thing you will do differently next time because of that lesson?`;
  }

  if (/what specific evidence supports that point\?/i.test(compact)) {
    return compact.replace(/what specific evidence supports that point\?/i, "What evidence supports that point?");
  }

  if (/what was the main reason for that choice compared with the alternative\?/i.test(compact)) {
    return compact.replace(
      /what was the main reason for that choice compared with the alternative\?/i,
      "Why did you choose that instead of the other option?",
    );
  }

  return compact
    .replace(/\bWhat specifically can you\b/g, "What can you")
    .replace(/\bwhat specifically can you\b/g, "what can you")
    .replace(/\bWhat specific\b/g, "What")
    .replace(/\bwhat specific\b/g, "what")
    .replace(/\bconcrete\b/g, "clear")
    .replace(/\bpersonally\b/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s+\?/g, "?")
    .trim();
}

export default function PresentPage() {
  const [projectContext, setProjectContext] = useState<ProjectContext>(defaultProjectContext);
  const [professorConfig, setProfessorConfig] = useState<ProfessorConfig>();
  const [sessionId, setSessionId] = useState<string>();
  const [uploadedFilename, setUploadedFilename] = useState<string>();
  const [slides, setSlides] = useState<Slide[]>([]);
  const [preparedQuestions, setPreparedQuestions] = useState<PreparedQuestion[]>([]);
  const [questionSource, setQuestionSource] = useState<"llm" | "heuristic" | undefined>(undefined);
  const [questionCacheHit, setQuestionCacheHit] = useState(false);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [slideMode, setSlideMode] = useState<SlideMode>("auto");
  const [transcript, setTranscript] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [queuedFeedback, setQueuedFeedback] = useState<FeedbackItem>();
  const [activeChunk, setActiveChunk] = useState("");
  const [livePreview, setLivePreview] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [unseenCount, setUnseenCount] = useState(0);
  const [latestFeedbackRephrase, setLatestFeedbackRephrase] = useState<string>();
  const [status, setStatus] = useState("Ready for live presentation mode.");
  const [busy, setBusy] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [liveConnecting, setLiveConnecting] = useState(false);
  const [liveConnected, setLiveConnected] = useState(false);
  const [mode, setMode] = useState<"idle" | "live">("idle");
  const [liveStatus, setLiveStatus] = useState<"idle" | "connecting" | "listening" | "silent" | "analyzing" | "error">("idle");
  const [liveErrorMessage, setLiveErrorMessage] = useState("");
  const [debugStats, setDebugStats] = useState({
    socketOpened: 0,
    audioChunksSent: 0,
    audioBytesSent: 0,
    transcriptEvents: 0,
    finalChunksAnalyzed: 0,
    proxyMessages: 0,
    wsCloseEvents: 0,
    micTrackEnded: 0,
    audioContextState: "none",
    lastStopReason: "",
    lastCloseCode: undefined as number | undefined,
  });
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const muteNodeRef = useRef<GainNode | null>(null);
  const transcriptRef = useRef<string[]>([]);
  const recentFeedbackRef = useRef<string[]>([]);
  const currentSlideRef = useRef<Slide | undefined>(undefined);
  const projectContextRef = useRef<ProjectContext>(defaultProjectContext);
  const preparedQuestionsRef = useRef<PreparedQuestion[]>([]);
  const latestFeedbackRef = useRef<FeedbackItem | undefined>(undefined);
  const studentCoverageRef = useRef<Record<string, number>>({});
  const slideModeRef = useRef<SlideMode>("auto");
  const sessionIdRef = useRef<string | undefined>(undefined);
  const liveStateRef = useRef({ connected: false, connecting: false });
  const voiceEnabledRef = useRef(true);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pendingChunksRef = useRef<string[]>([]);
  const drainingRunRef = useRef<number | null>(null);
  const drawerOpenTimerRef = useRef<NodeJS.Timeout | null>(null);
  const spokenFeedbackIdsRef = useRef<Set<string>>(new Set());
  const speechAudioRef = useRef<HTMLAudioElement | null>(null);
  const speechAudioUrlRef = useRef<string | null>(null);
  const ttsSocketRef = useRef<WebSocket | null>(null);
  const ttsAudioContextRef = useRef<AudioContext | null>(null);
  const ttsPlaybackTimeRef = useRef(0);
  const ttsGenerationRef = useRef(0);
  const ttsSourceNodesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const lastAnalyzeAtRef = useRef(0);
  const liveErrorMessageRef = useRef("");
  const lastForcedTurnWordCountRef = useRef(0);
  const liveRunTokenRef = useRef(0);

  const latestFeedback = [...feedback].reverse().find((item) => !item.resolved && item.deliveryStatus !== "queued");
  const recentFeedback = useMemo(() => feedback.slice(-5).map((item) => item.message), [feedback]);
  const currentSlide = slides[currentSlideIndex];
  const LIVE_ANALYZE_MIN_GAP_MS = 1400;
  const LIVE_SILENCE_MS = 2800;
  const SLIDE_ANALYSIS_CHAR_LIMIT = 700;

  function compactSlideForAnalysis(slide: Slide): Slide {
    return {
      ...slide,
      content: slide.content.length > SLIDE_ANALYSIS_CHAR_LIMIT
        ? `${slide.content.slice(0, SLIDE_ANALYSIS_CHAR_LIMIT)}...`
        : slide.content,
    };
  }

  function questionsForAnalysis(activeSlide?: Slide): PreparedQuestion[] {
    if (!activeSlide) {
      return preparedQuestionsRef.current.slice(0, 8);
    }

    const nearbySlideNumbers = new Set([
      activeSlide.slideNumber - 1,
      activeSlide.slideNumber,
      activeSlide.slideNumber + 1,
    ]);
    return preparedQuestionsRef.current.filter((question) => nearbySlideNumbers.has(question.slideNumber)).slice(0, 9);
  }

  function slidesForAnalysis(): Slide[] {
    return slides.map(compactSlideForAnalysis);
  }

  function clearDrawerOpenTimer() {
    if (drawerOpenTimerRef.current) {
      clearTimeout(drawerOpenTimerRef.current);
      drawerOpenTimerRef.current = null;
    }
  }

  function goToSlideIndex(index: number) {
    if (slides.length === 0) {
      return;
    }
    const nextIndex = Math.max(0, Math.min(slides.length - 1, index));
    currentSlideRef.current = slides[nextIndex];
    setCurrentSlideIndex(nextIndex);
  }

  function setTrackingMode(mode: SlideMode) {
    slideModeRef.current = mode;
    setSlideMode(mode);
  }

  function jumpToSlide(slideNumber: number) {
    const targetIndex = slides.findIndex((slide) => slide.slideNumber === slideNumber);
    if (targetIndex >= 0) {
      setTrackingMode("manual");
      goToSlideIndex(targetIndex);
      setStatus(`Locked to slide ${slideNumber} in manual mode.`);
    }
  }

  function stopSpeaking() {
    ttsGenerationRef.current += 1;
    if (ttsSocketRef.current) {
      try {
        if (ttsSocketRef.current.readyState === WebSocket.OPEN) {
          ttsSocketRef.current.send("__close__");
        }
        ttsSocketRef.current.close();
      } catch {
        // Ignore cleanup failures while interrupting speech.
      }
      ttsSocketRef.current = null;
    }
    ttsSourceNodesRef.current.forEach((source) => {
      try {
        source.stop();
      } catch {
        // Ignore sources that already ended.
      }
      source.disconnect();
    });
    ttsSourceNodesRef.current.clear();
    ttsPlaybackTimeRef.current = 0;
    if (speechAudioRef.current) {
      speechAudioRef.current.pause();
      speechAudioRef.current = null;
    }
    if (speechAudioUrlRef.current) {
      URL.revokeObjectURL(speechAudioUrlRef.current);
      speechAudioUrlRef.current = null;
    }
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      return;
    }
    window.speechSynthesis.cancel();
  }

  async function ensureTtsAudioContext(): Promise<AudioContext> {
    const existing = ttsAudioContextRef.current;
    if (existing && existing.state !== "closed") {
      if (existing.state === "suspended") {
        await existing.resume();
      }
      return existing;
    }

    const context = new AudioContext({ sampleRate: DEEPGRAM_TTS_SAMPLE_RATE });
    if (context.state === "suspended") {
      await context.resume();
    }
    ttsAudioContextRef.current = context;
    return context;
  }

  function playPcmChunk(chunk: ArrayBuffer, generation: number) {
    if (generation !== ttsGenerationRef.current) {
      return;
    }

    const context = ttsAudioContextRef.current;
    if (!context || context.state === "closed") {
      return;
    }

    const pcm16 = new Int16Array(chunk);
    if (pcm16.length === 0) {
      return;
    }

    const audioBuffer = context.createBuffer(1, pcm16.length, DEEPGRAM_TTS_SAMPLE_RATE);
    const samples = audioBuffer.getChannelData(0);
    for (let i = 0; i < pcm16.length; i += 1) {
      samples[i] = pcm16[i] / 0x8000;
    }

    const source = context.createBufferSource();
    source.buffer = audioBuffer;
    source.playbackRate.value = FACULTY_TTS_PLAYBACK_RATE;
    source.connect(context.destination);
    const startAt = Math.max(context.currentTime + 0.01, ttsPlaybackTimeRef.current || 0);
    source.start(startAt);
    ttsPlaybackTimeRef.current = startAt + (audioBuffer.duration / FACULTY_TTS_PLAYBACK_RATE);
    ttsSourceNodesRef.current.add(source);
    source.addEventListener("ended", () => {
      ttsSourceNodesRef.current.delete(source);
      source.disconnect();
    }, { once: true });
  }

  async function speakWithDeepgramVoice(text: string) {
    stopSpeaking();
    const generation = ttsGenerationRef.current;
    const speechText = normalizeTextForSpeech(text);

    try {
      const context = await ensureTtsAudioContext();
      ttsPlaybackTimeRef.current = Math.max(context.currentTime + 0.02, 0);

      await new Promise<void>((resolve, reject) => {
        const socket = new WebSocket(getDeepgramTtsStreamUrl());
        socket.binaryType = "arraybuffer";
        ttsSocketRef.current = socket;
        let opened = false;
        let receivedAudio = false;
        let flushed = false;

        const cleanup = () => {
          if (ttsSocketRef.current === socket) {
            ttsSocketRef.current = null;
          }
        };

        socket.addEventListener("open", () => {
          opened = true;
          socket.send(JSON.stringify({ type: "Speak", text: speechText }));
          socket.send(JSON.stringify({ type: "Flush" }));
        });

        socket.addEventListener("message", (event) => {
          if (generation !== ttsGenerationRef.current) {
            socket.close();
            return;
          }

          if (typeof event.data !== "string") {
            receivedAudio = true;
            playPcmChunk(event.data as ArrayBuffer, generation);
            if (!flushed) {
              resolve();
            }
            return;
          }

          let payload: { type?: string; message?: string };
          try {
            payload = JSON.parse(event.data) as typeof payload;
          } catch {
            return;
          }

          if (payload.type === "error") {
            cleanup();
            reject(new Error(payload.message ?? "Deepgram streaming TTS failed."));
            socket.close();
            return;
          }

          if (payload.type === "Flushed") {
            flushed = true;
            setTimeout(() => {
              if (socket.readyState === WebSocket.OPEN) {
                socket.send("__close__");
                socket.close();
              }
            }, 150);
          }
        });

        socket.addEventListener("close", () => {
          cleanup();
          if (!opened) {
            reject(new Error("Deepgram streaming TTS could not connect."));
            return;
          }
          if (!receivedAudio && generation === ttsGenerationRef.current) {
            reject(new Error("Deepgram streaming TTS returned no audio."));
          }
        });

        socket.addEventListener("error", () => {
          cleanup();
          reject(new Error("Deepgram streaming TTS failed."));
        });
      });
      return;
    } catch {
      const audio = await synthesizeDeepgramSpeech(speechText);
      stopSpeaking();
      const url = URL.createObjectURL(audio);
      const element = new Audio(url);
      element.playbackRate = FACULTY_TTS_PLAYBACK_RATE;
      speechAudioRef.current = element;
      speechAudioUrlRef.current = url;
      element.addEventListener("ended", () => {
        URL.revokeObjectURL(url);
        if (speechAudioUrlRef.current === url) {
          speechAudioUrlRef.current = null;
        }
        if (speechAudioRef.current === element) {
          speechAudioRef.current = null;
        }
      }, { once: true });
      await element.play();
    }
  }

  function isRepeatRequest(text: string) {
    return REPEAT_REQUEST_PATTERNS.some((pattern) => pattern.test(text));
  }

  function isQuestionConfirmation(text: string) {
    return QUESTION_CONFIRMATION_PATTERNS.some((pattern) => pattern.test(text));
  }

  function isQuestionRephraseRequest(text: string) {
    return QUESTION_REPHRASE_PATTERNS.some((pattern) => pattern.test(text));
  }

  function speakFacultyQuestion(item: FeedbackItem, force = false, rawQuestionOnly = false) {
    if (!voiceEnabledRef.current || typeof window === "undefined") {
      return;
    }

    const speechKey = item.sourceQuestionId ?? item.createdAt;
    if (!force && spokenFeedbackIdsRef.current.has(speechKey)) {
      return;
    }

    spokenFeedbackIdsRef.current.add(speechKey);
    const spokenText = rawQuestionOnly ? item.message : `${FACULTY_TTS_OPENER} ${item.message}`;
    void speakWithDeepgramVoice(spokenText).catch(() => undefined);
  }

  function repeatLatestQuestion(requestText: string) {
    if (!isRepeatRequest(requestText)) {
      return false;
    }

    const latestUnresolvedFeedback = latestFeedbackRef.current;
    if (!latestUnresolvedFeedback) {
      return false;
    }

    clearDrawerOpenTimer();
    setDrawerOpen(true);
    setUnseenCount(0);
    stopSpeaking();
    speakFacultyQuestion(latestUnresolvedFeedback, true, true);
    setStatus("Repeated the latest faculty question.");
    return true;
  }

  async function rephraseLatestQuestion(requestText: string, runToken: number) {
    if (!isQuestionRephraseRequest(requestText)) {
      return false;
    }

    const latestUnresolvedFeedback = latestFeedbackRef.current;
    if (!latestUnresolvedFeedback) {
      return false;
    }

    clearDrawerOpenTimer();
    setDrawerOpen(true);
    setUnseenCount(0);
    stopSpeaking();
    const heuristicQuestion = simplifyQuestionText(latestUnresolvedFeedback.message);
    let simplifiedQuestion = heuristicQuestion;
    try {
      const result = await rephraseFacultyQuestion(latestUnresolvedFeedback.message);
      const candidate = result.rephrasedQuestion.trim();
      const originalNormalized = normalizeQuestionForComparison(latestUnresolvedFeedback.message);
      const candidateNormalized = normalizeQuestionForComparison(candidate);
      const heuristicNormalized = normalizeQuestionForComparison(heuristicQuestion);
      if (candidateNormalized && candidateNormalized !== originalNormalized && candidateNormalized !== heuristicNormalized) {
        simplifiedQuestion = candidate;
      }
    } catch {
      // Fall back to the local rewrite when the lightweight LLM rephrase path is unavailable.
    }

    if (runToken !== liveRunTokenRef.current) {
      return true;
    }
    setLatestFeedbackRephrase(simplifiedQuestion);
    if (websocketRef.current) {
      void speakWithDeepgramVoice(`${FACULTY_TTS_REPHRASE_OPENER} ${simplifiedQuestion}`).catch(() => undefined);
    }
    setStatus("Rephrased the latest faculty question.");
    return true;
  }

  function queueFacultyQuestionReveal(item: FeedbackItem) {
    clearDrawerOpenTimer();
    setDrawerOpen(true);
    setUnseenCount(0);
    speakFacultyQuestion(item);
  }

  function acknowledgeResolvedQuestion(requestText: string, resolvedFeedback?: FeedbackItem) {
    if (!resolvedFeedback || !isQuestionConfirmation(requestText) || typeof window === "undefined") {
      return false;
    }

    stopSpeaking();
    void speakWithDeepgramVoice(FACULTY_ACKNOWLEDGMENT).catch(() => undefined);
    setStatus("Faculty acknowledged the presenter response.");
    return true;
  }

  function applyResolvedFeedback(resolvedFeedback?: FeedbackItem) {
    if (!resolvedFeedback) {
      return;
    }

    setFeedback((current) =>
      current.map((item) => (item.createdAt === resolvedFeedback.createdAt ? resolvedFeedback : item)),
    );
    setUnseenCount((current) => Math.max(0, current - 1));
  }

  function resetRunState() {
    pendingChunksRef.current = [];
    lastAnalyzeAtRef.current = 0;
    setSessionId(undefined);
    sessionIdRef.current = undefined;
    setTranscript([]);
    transcriptRef.current = [];
    setFeedback([]);
    setQueuedFeedback(undefined);
    setLatestFeedbackRephrase(undefined);
    studentCoverageRef.current = {};
    latestFeedbackRef.current = undefined;
    spokenFeedbackIdsRef.current = new Set();
    stopSpeaking();
    setActiveChunk("");
    setLivePreview("");
    setDrawerOpen(false);
    clearDrawerOpenTimer();
    setUnseenCount(0);
    setLiveErrorMessage("");
    liveErrorMessageRef.current = "";
    lastForcedTurnWordCountRef.current = 0;
    setDebugStats({
      socketOpened: 0,
      audioChunksSent: 0,
      audioBytesSent: 0,
      transcriptEvents: 0,
      finalChunksAnalyzed: 0,
      proxyMessages: 0,
      wsCloseEvents: 0,
      micTrackEnded: 0,
      audioContextState: "none",
      lastStopReason: "",
      lastCloseCode: undefined,
    });
  }

  function resetSilenceTimer() {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
    }
    if (!websocketRef.current) {
      return;
    }
    silenceTimerRef.current = setTimeout(() => {
      if (liveStateRef.current.connected) {
        setLiveStatus("silent");
      }
    }, LIVE_SILENCE_MS);
  }

  function downsampleTo16kHz(input: Float32Array, inputSampleRate: number): Int16Array {
    if (inputSampleRate === 16000) {
      const output = new Int16Array(input.length);
      for (let i = 0; i < input.length; i += 1) {
        const sample = Math.max(-1, Math.min(1, input[i]));
        output[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      }
      return output;
    }

    const ratio = inputSampleRate / 16000;
    const outputLength = Math.max(1, Math.round(input.length / ratio));
    const output = new Int16Array(outputLength);
    let offsetResult = 0;
    let offsetBuffer = 0;

    while (offsetResult < output.length) {
      const nextOffsetBuffer = Math.min(input.length, Math.round((offsetResult + 1) * ratio));
      let accum = 0;
      let count = 0;

      for (let i = offsetBuffer; i < nextOffsetBuffer; i += 1) {
        accum += input[i];
        count += 1;
      }

      const sample = count > 0 ? accum / count : 0;
      const clamped = Math.max(-1, Math.min(1, sample));
      output[offsetResult] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;

      offsetResult += 1;
      offsetBuffer = nextOffsetBuffer;
    }

    return output;
  }

  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  useEffect(() => {
    recentFeedbackRef.current = recentFeedback;
  }, [recentFeedback]);

  useEffect(() => {
    currentSlideRef.current = currentSlide;
  }, [currentSlide]);

  useEffect(() => {
    projectContextRef.current = projectContext;
  }, [projectContext]);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    preparedQuestionsRef.current = preparedQuestions;
  }, [preparedQuestions]);

  useEffect(() => {
    latestFeedbackRef.current = latestFeedback;
  }, [latestFeedback]);

  useEffect(() => {
    slideModeRef.current = slideMode;
  }, [slideMode]);

  useEffect(() => {
    voiceEnabledRef.current = voiceEnabled;
  }, [voiceEnabled]);

  useEffect(() => {
    liveStateRef.current = { connected: liveConnected, connecting: liveConnecting };
  }, [liveConnected, liveConnecting]);

  useEffect(() => {
    getProfessorConfig()
      .then((config) => {
        setProfessorConfig(config);
        setProjectContext({
          title: config.assignmentName,
          summary: config.assignmentContext,
          stack: [],
          goals: [],
          rubric: config.rubric,
          notes: config.questionStyle,
        });
        setStatus("Professor rubric loaded. Upload a .pptx to prepare slide questions.");
      })
      .catch((error) => setStatus(error instanceof Error ? error.message : "Unable to load professor setup."));
  }, []);

  async function ensureSession(runToken: number): Promise<string> {
    if (sessionIdRef.current) {
      return sessionIdRef.current;
    }
    const id = await startSession(projectContextRef.current);
    if (runToken === liveRunTokenRef.current) {
      sessionIdRef.current = id;
      setSessionId(id);
    }
    return id;
  }

  async function analyzeTranscriptChunk(nextChunk: string, runToken: number) {
    if (websocketRef.current) {
      setLiveStatus("analyzing");
    }
    setDebugStats((current) => ({
      ...current,
      finalChunksAnalyzed: current.finalChunksAnalyzed + 1,
    }));
    const id = await ensureSession(runToken);
    if (runToken !== liveRunTokenRef.current) {
      return;
    }
    const previousTranscript = transcriptRef.current;
    const nextTranscript = [...previousTranscript, nextChunk];
    setTranscript(nextTranscript);
    transcriptRef.current = nextTranscript;
    setActiveChunk(nextChunk);
    setLivePreview("");

    if (websocketRef.current && (repeatLatestQuestion(nextChunk) || await rephraseLatestQuestion(nextChunk, runToken))) {
      if (runToken === liveRunTokenRef.current && websocketRef.current) {
        setLiveStatus("listening");
        resetSilenceTimer();
      }
      return;
    }
    if (runToken !== liveRunTokenRef.current) {
      return;
    }

    const result = await analyzeChunk({
      sessionId: id,
      transcriptChunk: nextChunk,
      recentTranscript: previousTranscript.slice(-4),
      recentFeedback: recentFeedbackRef.current,
      projectContext: projectContextRef.current,
      currentSlide: currentSlideRef.current ? compactSlideForAnalysis(currentSlideRef.current) : undefined,
      slideMode: slideModeRef.current,
      presentationSlides: slidesForAnalysis(),
      preparedQuestions: questionsForAnalysis(currentSlideRef.current),
      studentCoverage: studentCoverageRef.current,
    });
    if (runToken !== liveRunTokenRef.current) {
      return;
    }

    if (slideModeRef.current === "auto" && result.inferredCurrentSlide) {
      const inferredIndex = slides.findIndex((slide) => slide.slideNumber === result.inferredCurrentSlide?.slideNumber);
      if (inferredIndex >= 0) {
        currentSlideRef.current = slides[inferredIndex];
        setCurrentSlideIndex(inferredIndex);
      }
    }

    setQueuedFeedback(result.queuedFeedback);
    applyResolvedFeedback(result.resolvedFeedback);
    const acknowledgedResolution = websocketRef.current && acknowledgeResolvedQuestion(nextChunk, result.resolvedFeedback);

    if (websocketRef.current) {
      setLiveStatus("listening");
      resetSilenceTimer();
    }

    if (result.trigger && result.feedback) {
      setLatestFeedbackRephrase(undefined);
      if (result.feedback.targetStudent) {
        studentCoverageRef.current = {
          ...studentCoverageRef.current,
          [result.feedback.targetStudent]: (studentCoverageRef.current[result.feedback.targetStudent] ?? 0) + 1,
        };
      }
      setFeedback((current) => [...current, result.feedback as FeedbackItem]);
      if (websocketRef.current) {
        queueFacultyQuestionReveal(result.feedback);
      } else {
        setDrawerOpen(true);
      }
      setStatus("Faculty question triggered.");
      return;
    }

    setStatus(
      result.resolvedFeedback
        ? (acknowledgedResolution ? "Faculty acknowledged the presenter response." : "Faculty question auto-marked addressed.")
        : result.queuedFeedback
          ? (
            result.answerEvaluation?.shouldAskFollowUp
              ? "Faculty-AI queued one follow-up after a partial answer."
              : result.reason ?? "Faculty-AI queued a question for a better moment."
          )
        : result.reason ?? "No feedback triggered for this chunk.",
    );
  }

  async function drainLiveChunks(runToken: number) {
    drainingRunRef.current = runToken;
    try {
      while (runToken === liveRunTokenRef.current && pendingChunksRef.current.length > 0) {
        const delay = LIVE_ANALYZE_MIN_GAP_MS - (Date.now() - lastAnalyzeAtRef.current);
        if (delay > 0) {
          await new Promise<void>((resolve) => setTimeout(resolve, delay));
        }
        if (runToken !== liveRunTokenRef.current) {
          return;
        }
        const chunk = pendingChunksRef.current.shift();
        if (chunk === undefined) {
          return;
        }
        lastAnalyzeAtRef.current = Date.now();
        try {
          await analyzeTranscriptChunk(chunk, runToken);
        } catch (error: unknown) {
          if (runToken !== liveRunTokenRef.current) {
            return;
          }
          setLiveStatus("error");
          setStatus(
            error instanceof Error && error.message === "Failed to fetch"
              ? "Failed to fetch from the backend while analyzing live speech."
              : error instanceof Error
                ? error.message
                : "Unable to analyze live transcript.",
          );
        }
      }
    } finally {
      if (drainingRunRef.current === runToken) {
        drainingRunRef.current = null;
      }
    }
  }

  function scheduleLiveChunk(nextChunk: string) {
    const normalized = nextChunk.trim();
    if (normalized) {
      pendingChunksRef.current.push(normalized);
      const runToken = liveRunTokenRef.current;
      if (drainingRunRef.current !== runToken) {
        void drainLiveChunks(runToken);
      }
    }
  }

  function maybeForceAnalyzeLongTurn(transcriptText: string) {
    const normalized = transcriptText.trim();
    if (!normalized) {
      return;
    }

    const words = normalized.split(/\s+/);
    const wordCount = words.length;
    if (wordCount < LIVE_MAX_TURN_WORDS) {
      return;
    }

    const newWordsSinceLastForced = wordCount - lastForcedTurnWordCountRef.current;
    if (newWordsSinceLastForced < LIVE_FORCED_CHUNK_MIN_NEW_WORDS) {
      return;
    }

    scheduleLiveChunk(words.slice(lastForcedTurnWordCountRef.current).join(" "));
    lastForcedTurnWordCountRef.current = wordCount;
  }

  function stopLiveSpeech(
    reason = "Live microphone stopped.",
    closeSocket = true,
    nextLiveStatus: "idle" | "error" = "idle",
    finishPendingAnalysis = false,
  ) {
    if (!finishPendingAnalysis) {
      liveRunTokenRef.current += 1;
      pendingChunksRef.current = [];
    }
    setDebugStats((current) => ({
      ...current,
      lastStopReason: reason,
    }));
    scriptProcessorRef.current?.disconnect();
    scriptProcessorRef.current = null;
    audioSourceRef.current?.disconnect();
    audioSourceRef.current = null;
    muteNodeRef.current?.disconnect();
    muteNodeRef.current = null;
    void audioContextRef.current?.close().catch(() => undefined);
    audioContextRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;

    const socket = websocketRef.current;
    websocketRef.current = null;
    if (closeSocket && socket && socket.readyState !== WebSocket.CLOSED) {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send("__close__");
      }
      socket.close();
    }
    setLiveConnected(false);
    setLiveConnecting(false);
    setLiveStatus(nextLiveStatus);
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    clearDrawerOpenTimer();
    stopSpeaking();
    setLivePreview("");
    setMode("idle");
    if (!liveErrorMessageRef.current || nextLiveStatus !== "error") {
      setStatus(reason);
    }
  }

  async function startLiveSpeech() {
    if (slides.length === 0) {
      setStatus("Upload a .pptx before starting live microphone mode.");
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("This browser does not support microphone capture.");
      return;
    }

    resetRunState();
    liveRunTokenRef.current += 1;
    const runToken = liveRunTokenRef.current;
    setMode("live");
    setLiveConnecting(true);
    setLiveStatus("connecting");
    try {
      await ensureSession(runToken);
      if (runToken !== liveRunTokenRef.current) {
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (runToken !== liveRunTokenRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      mediaStreamRef.current = stream;
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(2048, 1, 1);
      const muteNode = audioContext.createGain();
      muteNode.gain.value = 0;
      const socket = new WebSocket(getSpeechProxyUrl());

      websocketRef.current = socket;
      audioSourceRef.current = source;
      scriptProcessorRef.current = processor;
      muteNodeRef.current = muteNode;
      setDebugStats((current) => ({
        ...current,
        audioContextState: audioContext.state,
      }));

      audioContext.onstatechange = () => {
        setDebugStats((current) => ({
          ...current,
          audioContextState: audioContext.state,
        }));
      };

      stream.getAudioTracks().forEach((track) => {
        track.addEventListener("ended", () => {
          if (runToken !== liveRunTokenRef.current || stream !== mediaStreamRef.current) {
            return;
          }
          setDebugStats((current) => ({
            ...current,
            micTrackEnded: current.micTrackEnded + 1,
          }));
          stopLiveSpeech("Microphone track ended.", true, "error");
        });
      });

      socket.addEventListener("open", () => {
        if (runToken !== liveRunTokenRef.current) {
          socket.close();
          return;
        }
        source.connect(processor);
        processor.connect(muteNode);
        muteNode.connect(audioContext.destination);
        setLiveConnected(true);
        setLiveConnecting(false);
        setLiveStatus("listening");
        resetSilenceTimer();
        setDebugStats((current) => ({
          ...current,
          socketOpened: current.socketOpened + 1,
        }));
        setStatus("Live microphone connected to backend speech proxy.");
      });

      socket.addEventListener("message", (event) => {
        if (runToken !== liveRunTokenRef.current || socket !== websocketRef.current) {
          return;
        }
        setDebugStats((current) => ({
          ...current,
          proxyMessages: current.proxyMessages + 1,
        }));
        let data: {
          type?: string;
          is_final?: boolean;
          speech_final?: boolean;
          event?: string;
          transcript?: string;
          code?: number;
          reason?: string;
          message?: string;
          channel?: { alternatives?: Array<{ transcript?: string }> };
        };

        try {
          data = JSON.parse(event.data) as typeof data;
        } catch {
          return;
        }

        if (data.type === "proxy_open") {
          return;
        }

        if (data.type === "error") {
          setLiveStatus("error");
          const message = data.message ?? "Speech proxy failed.";
          liveErrorMessageRef.current = message;
          setLiveErrorMessage(message);
          setStatus(message);
          stopLiveSpeech(message, false, "error");
          return;
        }

        if (data.type === "proxy_close") {
          setDebugStats((current) => ({
            ...current,
            lastCloseCode: data.code,
          }));
          const normalClose = !data.code || data.code === 1000 || data.code === 1001;
          stopLiveSpeech(
            normalClose
              ? "Live microphone stopped."
              : `Deepgram proxy closed (${data.code ?? 1006}).${data.reason ? ` ${data.reason}` : ""}`,
            false,
            normalClose ? "idle" : "error",
            normalClose,
          );
          return;
        }

        const isFluxTurnInfo = data.type === "TurnInfo";
        const isNovaResults = data.type === "Results";
        if (!isFluxTurnInfo && !isNovaResults) {
          return;
        }

        if (isFluxTurnInfo && data.event === "StartOfTurn") {
          lastForcedTurnWordCountRef.current = 0;
          return;
        }
        const transcriptText = isFluxTurnInfo
          ? data.transcript?.trim()
          : data.channel?.alternatives?.[0]?.transcript?.trim();
        if (!transcriptText) {
          return;
        }

        setLivePreview(transcriptText);
        setLiveStatus("listening");
        resetSilenceTimer();

        let completedText = transcriptText;
        if (isFluxTurnInfo) {
          if (data.event !== "EndOfTurn") {
            // EagerEndOfTurn can be followed by TurnResumed.
            maybeForceAnalyzeLongTurn(transcriptText);
            return;
          }

          completedText = transcriptText.split(/\s+/).slice(lastForcedTurnWordCountRef.current).join(" ");
          lastForcedTurnWordCountRef.current = 0;
        } else if (!data.is_final) {
          return;
        }

        setDebugStats((current) => ({
          ...current,
          transcriptEvents: current.transcriptEvents + 1,
        }));
        scheduleLiveChunk(completedText);
      });

      socket.addEventListener("error", () => {
        if (runToken !== liveRunTokenRef.current || socket !== websocketRef.current) {
          return;
        }
        liveErrorMessageRef.current = "Deepgram connection failed.";
        setLiveErrorMessage("Deepgram connection failed.");
        stopLiveSpeech("Deepgram connection failed.", true, "error");
      });

      socket.addEventListener("close", (event) => {
        if (runToken !== liveRunTokenRef.current || socket !== websocketRef.current) {
          return;
        }
        setDebugStats((current) => ({
          ...current,
          wsCloseEvents: current.wsCloseEvents + 1,
          lastCloseCode: event.code,
        }));
        const closeReason = event.reason?.trim();
        const detail = closeReason ? ` ${closeReason}` : "";
        const normalClose = event.code === 1000 || event.code === 1001;
        const message = liveErrorMessageRef.current
          || (normalClose ? "Live microphone stopped." : `Deepgram connection closed (${event.code}).${detail}`);
        stopLiveSpeech(message, false, normalClose ? "idle" : "error", normalClose);
      });

      processor.onaudioprocess = (event) => {
        if (runToken !== liveRunTokenRef.current) {
          return;
        }
        if (socket.readyState !== WebSocket.OPEN) {
          return;
        }

        const channelData = event.inputBuffer.getChannelData(0);
        if (!channelData || channelData.length === 0) {
          return;
        }

        const pcm16 = downsampleTo16kHz(channelData, audioContext.sampleRate);
        if (pcm16.byteLength === 0) {
          return;
        }

        socket.send(pcm16.buffer);
        setDebugStats((current) => ({
          ...current,
          audioChunksSent: current.audioChunksSent + 1,
          audioBytesSent: current.audioBytesSent + pcm16.byteLength,
        }));
      };
    } catch (error) {
      if (runToken !== liveRunTokenRef.current) {
        return;
      }
      const message = error instanceof Error && error.message === "Failed to fetch"
        ? "Failed to fetch from the backend. Confirm the API is running and NEXT_PUBLIC_API_BASE_URL is correct."
        : error instanceof Error
          ? error.message
          : "Unable to start live speech.";
      liveErrorMessageRef.current = message;
      setLiveErrorMessage(message);
      stopLiveSpeech(message, true, "error");
    }
  }

  function resetPresentation() {
    resetRunState();
    setSlides([]);
    setPreparedQuestions([]);
    setQuestionSource(undefined);
    setQuestionCacheHit(false);
    setCurrentSlideIndex(0);
    setTrackingMode("auto");
    setUploadedFilename(undefined);
    stopLiveSpeech("Ready for live presentation mode.");
    setMode("idle");
    setStatus("Ready for live presentation mode.");
  }

  function openDrawer() {
    clearDrawerOpenTimer();
    setDrawerOpen(true);
    setUnseenCount(0);
    if (latestFeedback) {
      speakFacultyQuestion(latestFeedback);
    }
  }

  function toggleVoice() {
    setVoiceEnabled((enabled) => {
      if (enabled) {
        stopSpeaking();
      }
      return !enabled;
    });
  }

  async function handleFeedbackResolution(item: FeedbackItem, resolved: boolean) {
    const activeSessionId = sessionIdRef.current;
    if (!activeSessionId) {
      return;
    }

    try {
      const updated = await updateFeedbackResolution({
        sessionId: activeSessionId,
        createdAt: item.createdAt,
        resolved,
        resolutionReason: resolved ? "Presenter addressed this faculty question." : undefined,
        sourceQuestionId: item.sourceQuestionId,
        message: item.message,
      });
      if (sessionIdRef.current !== activeSessionId) {
        return;
      }
      setFeedback(updated);
      if (latestFeedback?.createdAt === item.createdAt) {
        setLatestFeedbackRephrase(undefined);
      }
      if (resolved) {
        setQueuedFeedback((queued) => queued?.followUpToQuestionId === (item.sourceQuestionId || item.createdAt) ? undefined : queued);
        stopSpeaking();
      }
      setUnseenCount((current) => (resolved ? Math.max(0, current - 1) : current + 1));
      setStatus(resolved ? "Faculty question marked addressed." : "Faculty question reopened.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to update faculty question.");
    }
  }

  async function handleUpload(file: File) {
    setBusy(true);
    try {
      const result = await uploadPresentation(file);
      setSlides(result.slides);
      setPreparedQuestions(result.preparedQuestions);
      setQuestionSource(result.questionSource);
      setQuestionCacheHit(result.cacheHit);
      setCurrentSlideIndex(0);
      setTrackingMode("auto");
      setUploadedFilename(file.name);
      setStatus(
        `Prepared ${result.preparedQuestions.length} faculty questions from ${result.slides.length} slides using ${result.questionSource}${result.cacheHit ? " (cached)" : ""}.`
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to upload presentation.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => () => {
    clearDrawerOpenTimer();
    stopLiveSpeech("Live microphone stopped.");
    void ttsAudioContextRef.current?.close().catch(() => undefined);
  }, []);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="topbar-title">
          <p className="eyebrow">Faculty-AI</p>
          <h1>Presentation cockpit</h1>
          <p>Run live Q&A support without crowding the presenter view.</p>
        </div>
        <div className={`topbar-status ${liveStatus}`}>
          <span aria-hidden="true" />
          <p>{status}</p>
        </div>
      </header>

      <section className="session-summary" aria-label="Presentation setup summary">
        <div>
          <span>Deck</span>
          <strong>{uploadedFilename ? uploadedFilename : "Not uploaded"}</strong>
        </div>
        <div>
          <span>Questions</span>
          <strong>{preparedQuestions.length}</strong>
        </div>
        <div>
          <span>Mode</span>
          <strong>{mode === "idle" ? "Ready" : "Live"}</strong>
        </div>
        <div>
          <span>Open issues</span>
          <strong>{feedback.filter((item) => !item.resolved).length}</strong>
        </div>
      </section>

      <div className="workspace">
        <div className="left-rail">
          <PresentationUpload disabled={busy} filename={uploadedFilename} onUpload={(file) => void handleUpload(file)} />
          <SessionControls
            disabled={busy}
            liveConnected={liveConnected}
            liveConnecting={liveConnecting}
            liveStatus={liveStatus}
            sessionId={sessionId}
            voiceEnabled={voiceEnabled}
            onReset={resetPresentation}
            onStartLive={() => void startLiveSpeech()}
            onStopLive={() => stopLiveSpeech(undefined, true, "idle", true)}
            onToggleVoice={toggleVoice}
          />
          <section className="quiet-panel">
            <p className="eyebrow">Rubric</p>
            <p>{professorConfig?.assignmentName ?? "Project Presentation"}</p>
            <small>{(professorConfig?.rubric ?? projectContext.rubric).join(", ")}</small>
            {questionSource ? <small>Questions: {questionSource}{questionCacheHit ? " cached" : ""}</small> : null}
          </section>
        </div>

        <div className="main-stage">
          <SlideTracker
            currentSlideIndex={currentSlideIndex}
            preparedQuestions={preparedQuestions}
            slideMode={slideMode}
            slides={slides}
            onModeChange={(mode) => {
              setTrackingMode(mode);
              setStatus(mode === "manual" ? "Manual slide mode enabled." : "Auto slide mode enabled.");
            }}
            onJumpToSlide={jumpToSlide}
            onPrevious={() => {
              setTrackingMode("manual");
              goToSlideIndex(currentSlideIndex - 1);
            }}
            onNext={() => {
              setTrackingMode("manual");
              goToSlideIndex(currentSlideIndex + 1);
            }}
          />
          <TranscriptPanel
            activeChunk={activeChunk}
            debugStats={debugStats}
            livePreview={livePreview}
            liveStatus={liveStatus}
            transcript={transcript}
          />
        </div>
      </div>

      <FeedbackDrawer
        feedback={feedback}
        queuedFeedback={queuedFeedback}
        latestFeedback={latestFeedback}
        latestFeedbackRephrase={latestFeedback && !latestFeedback.resolved ? latestFeedbackRephrase : undefined}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onResolve={(item, resolved) => void handleFeedbackResolution(item, resolved)}
      />
      <FacultyAlert latestFeedback={latestFeedback} open={drawerOpen} unseenCount={unseenCount} onOpen={openDrawer} />
    </main>
  );
}
