"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { FacultyAlert } from "@/components/FacultyAlert";
import { FeedbackDrawer } from "@/components/FeedbackDrawer";
import { PresentationUpload } from "@/components/PresentationUpload";
import { SessionControls } from "@/components/SessionControls";
import { SlideTracker } from "@/components/SlideTracker";
import { TranscriptPanel } from "@/components/TranscriptPanel";
import { analyzeChunk, getProfessorConfig, getSpeechProxyUrl, startSession, uploadPresentation } from "@/lib/api";
import { finalizeSession } from "@/lib/api";
import { demoTranscriptChunks } from "@/lib/demoTranscript";
import type { FeedbackItem, FinalEvaluation, PreparedQuestion, ProfessorConfig, ProjectContext, Slide } from "@/lib/types";

const defaultProjectContext: ProjectContext = {
  title: "Project Presentation",
  summary: "",
  stack: [],
  goals: [],
  rubric: ["clarity", "technical justification", "evaluation"],
  notes: "",
};

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
  const [transcript, setTranscript] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [finalEvaluation, setFinalEvaluation] = useState<FinalEvaluation>();
  const [activeChunk, setActiveChunk] = useState("");
  const [livePreview, setLivePreview] = useState("");
  const [chunkIndex, setChunkIndex] = useState(0);
  const [running, setRunning] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [unseenCount, setUnseenCount] = useState(0);
  const [status, setStatus] = useState("Ready for fake transcript mode.");
  const [busy, setBusy] = useState(false);
  const [liveConnecting, setLiveConnecting] = useState(false);
  const [liveConnected, setLiveConnected] = useState(false);
  const [mode, setMode] = useState<"idle" | "demo" | "live">("idle");
  const [liveStatus, setLiveStatus] = useState<"idle" | "connecting" | "listening" | "silent" | "analyzing" | "error">("idle");
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
  const timerRef = useRef<NodeJS.Timeout | null>(null);
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
  const liveStateRef = useRef({ connected: false, connecting: false });
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pendingChunkRef = useRef<string | null>(null);
  const pendingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const keepAliveTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastAnalyzeAtRef = useRef(0);

  const latestFeedback = feedback[feedback.length - 1];
  const recentFeedback = useMemo(() => feedback.slice(-5).map((item) => item.message), [feedback]);
  const currentSlide = slides[currentSlideIndex];
  const LIVE_ANALYZE_MIN_GAP_MS = 1400;
  const LIVE_SILENCE_MS = 2800;

  function resetRunState() {
    setSessionId(undefined);
    setTranscript([]);
    transcriptRef.current = [];
    setFeedback([]);
    setFinalEvaluation(undefined);
    setActiveChunk("");
    setLivePreview("");
    setChunkIndex(0);
    setDrawerOpen(false);
    setUnseenCount(0);
    setRunning(false);
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
    preparedQuestionsRef.current = preparedQuestions;
  }, [preparedQuestions]);

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

  async function ensureSession(): Promise<string> {
    if (sessionId) {
      return sessionId;
    }
    const id = await startSession(projectContextRef.current);
    setSessionId(id);
    return id;
  }

  async function sendNextChunk() {
    if (busy) {
      return;
    }

    const nextChunk = demoTranscriptChunks[chunkIndex];
    if (!nextChunk) {
      setRunning(false);
      setStatus("Demo transcript complete.");
      return;
    }

    setBusy(true);
    try {
      const id = await ensureSession();
      const nextTranscript = [...transcriptRef.current, nextChunk];
      setTranscript(nextTranscript);
      transcriptRef.current = nextTranscript;
      setActiveChunk(nextChunk);
      setChunkIndex((current) => current + 1);

      const result = await analyzeChunk({
        sessionId: id,
        transcriptChunk: nextChunk,
        recentTranscript: nextTranscript.slice(-4),
        recentFeedback: recentFeedbackRef.current,
        projectContext: projectContextRef.current,
        currentSlide: currentSlideRef.current,
        presentationSlides: slides,
        preparedQuestions: preparedQuestionsRef.current,
      });

      if (result.inferredCurrentSlide) {
        const inferredIndex = slides.findIndex((slide) => slide.slideNumber === result.inferredCurrentSlide?.slideNumber);
        if (inferredIndex >= 0) {
          setCurrentSlideIndex(inferredIndex);
        }
      }

      if (result.trigger && result.feedback) {
        setFeedback((current) => [...current, result.feedback as FeedbackItem]);
        setDrawerOpen(true);
        setUnseenCount((current) => current + 1);
        setStatus("Faculty alert triggered.");
      } else {
        setStatus(result.reason ?? "No feedback triggered for this chunk.");
      }
    } catch (error) {
      setRunning(false);
      setStatus(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function analyzeTranscriptChunk(nextChunk: string) {
    setLiveStatus("analyzing");
    setDebugStats((current) => ({
      ...current,
      finalChunksAnalyzed: current.finalChunksAnalyzed + 1,
    }));
    const id = await ensureSession();
    const nextTranscript = [...transcriptRef.current, nextChunk];
    setTranscript(nextTranscript);
    transcriptRef.current = nextTranscript;
    setActiveChunk(nextChunk);
    setLivePreview("");

    const result = await analyzeChunk({
      sessionId: id,
      transcriptChunk: nextChunk,
      recentTranscript: nextTranscript.slice(-4),
      recentFeedback: recentFeedbackRef.current,
      projectContext: projectContextRef.current,
      currentSlide: currentSlideRef.current,
      presentationSlides: slides,
      preparedQuestions: preparedQuestionsRef.current,
    });

    if (result.inferredCurrentSlide) {
      const inferredIndex = slides.findIndex((slide) => slide.slideNumber === result.inferredCurrentSlide?.slideNumber);
      if (inferredIndex >= 0) {
        setCurrentSlideIndex(inferredIndex);
      }
    }

    if (result.trigger && result.feedback) {
      setFeedback((current) => [...current, result.feedback as FeedbackItem]);
      setDrawerOpen(true);
      setUnseenCount((current) => current + 1);
      setStatus("Live faculty question triggered.");
      setLiveStatus("listening");
      resetSilenceTimer();
      return;
    }

    setLiveStatus("listening");
    resetSilenceTimer();
    setStatus(result.reason ?? "No feedback triggered for this chunk.");
  }

  function scheduleLiveChunk(nextChunk: string) {
    const normalized = nextChunk.trim();
    if (!normalized) {
      return;
    }

    const elapsed = Date.now() - lastAnalyzeAtRef.current;
    if (elapsed >= LIVE_ANALYZE_MIN_GAP_MS && !pendingTimerRef.current) {
      lastAnalyzeAtRef.current = Date.now();
      void analyzeTranscriptChunk(normalized).catch((error: unknown) => {
        setLiveStatus("error");
        setStatus(
          error instanceof Error && error.message === "Failed to fetch"
            ? "Failed to fetch from the backend while analyzing live speech."
            : error instanceof Error
              ? error.message
              : "Unable to analyze live transcript.",
        );
      });
      return;
    }

    pendingChunkRef.current = normalized;
    if (pendingTimerRef.current) {
      return;
    }

    const delay = Math.max(200, LIVE_ANALYZE_MIN_GAP_MS - elapsed);
    pendingTimerRef.current = setTimeout(() => {
      pendingTimerRef.current = null;
      const queuedChunk = pendingChunkRef.current;
      pendingChunkRef.current = null;
      if (!queuedChunk) {
        return;
      }
      lastAnalyzeAtRef.current = Date.now();
      void analyzeTranscriptChunk(queuedChunk).catch((error: unknown) => {
        setLiveStatus("error");
        setStatus(
          error instanceof Error && error.message === "Failed to fetch"
            ? "Failed to fetch from the backend while analyzing live speech."
            : error instanceof Error
              ? error.message
              : "Unable to analyze live transcript.",
        );
      });
    }, delay);
  }

  function stopLiveSpeech(
    reason = "Live microphone stopped.",
    closeSocket = true,
    nextLiveStatus: "idle" | "error" = "idle",
  ) {
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
    if (closeSocket && socket && socket.readyState === WebSocket.OPEN) {
      socket.send("__close__");
      socket.close();
    }
    setLiveConnected(false);
    setLiveConnecting(false);
    setLiveStatus(nextLiveStatus);
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (pendingTimerRef.current) {
      clearTimeout(pendingTimerRef.current);
      pendingTimerRef.current = null;
    }
    if (keepAliveTimerRef.current) {
      clearInterval(keepAliveTimerRef.current);
      keepAliveTimerRef.current = null;
    }
    pendingChunkRef.current = null;
    setLivePreview("");
    if (nextLiveStatus === "idle" && mode === "live") {
      setMode("idle");
    }
    setStatus(reason);
  }

  async function startLiveSpeech() {
    if (running) {
      setStatus("Pause demo mode before starting live microphone capture.");
      return;
    }

    if (slides.length === 0) {
      setStatus("Upload a .pptx before starting live microphone mode.");
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("This browser does not support microphone capture.");
      return;
    }

    if (typeof window === "undefined" || typeof MediaRecorder === "undefined") {
      setStatus("This browser does not support live audio recording.");
      return;
    }

    resetRunState();
    setMode("live");
    setLiveConnecting(true);
    setLiveStatus("connecting");
    try {
      await ensureSession();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(2048, 1, 1);
      const muteNode = audioContext.createGain();
      muteNode.gain.value = 0;
      const socket = new WebSocket(getSpeechProxyUrl());

      mediaStreamRef.current = stream;
      websocketRef.current = socket;
      audioContextRef.current = audioContext;
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
          setDebugStats((current) => ({
            ...current,
            micTrackEnded: current.micTrackEnded + 1,
          }));
          stopLiveSpeech("Microphone track ended.", false, "error");
        });
      });

      socket.addEventListener("open", () => {
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
        setDebugStats((current) => ({
          ...current,
          proxyMessages: current.proxyMessages + 1,
        }));
        let data: {
          type?: string;
          is_final?: boolean;
          speech_final?: boolean;
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
          stopLiveSpeech(data.message ?? "Speech proxy failed.", false, "error");
          return;
        }

        if (data.type === "proxy_close") {
          setDebugStats((current) => ({
            ...current,
            lastCloseCode: data.code,
          }));
          stopLiveSpeech(
            `Deepgram proxy closed (${data.code ?? 1006}).${data.reason ? ` ${data.reason}` : ""}`,
            false,
            data.code === 1000 ? "idle" : "error",
          );
          return;
        }

        if (data.type !== "Results") {
          return;
        }

        const transcriptText = data.channel?.alternatives?.[0]?.transcript?.trim();
        if (!transcriptText) {
          return;
        }

        setLivePreview(transcriptText);
        setLiveStatus("listening");
        resetSilenceTimer();

        if (!data.is_final) {
          return;
        }

        setDebugStats((current) => ({
          ...current,
          transcriptEvents: current.transcriptEvents + 1,
        }));
        scheduleLiveChunk(transcriptText);
      });

      socket.addEventListener("error", () => {
        stopLiveSpeech("Deepgram connection failed.", true, "error");
      });

      socket.addEventListener("close", (event) => {
        setDebugStats((current) => ({
          ...current,
          wsCloseEvents: current.wsCloseEvents + 1,
          lastCloseCode: event.code,
        }));
        const closeReason = event.reason?.trim();
        const detail = closeReason ? ` ${closeReason}` : "";
        if (liveStateRef.current.connected || liveStateRef.current.connecting) {
          stopLiveSpeech(
            `Deepgram connection closed (${event.code}).${detail}`,
            false,
            event.code === 1000 ? "idle" : "error",
          );
        }
      });

      processor.onaudioprocess = (event) => {
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
      const message = error instanceof Error && error.message === "Failed to fetch"
        ? "Failed to fetch from the backend. Confirm the API is running and NEXT_PUBLIC_API_BASE_URL is correct."
        : error instanceof Error
          ? error.message
          : "Unable to start live speech.";
      stopLiveSpeech(message, true, "error");
    }
  }

  function startDemo() {
    if (liveConnected || liveConnecting) {
      setStatus("Stop live microphone mode before starting the fake transcript demo.");
      return;
    }
    if (slides.length === 0) {
      setStatus("Upload a .pptx before starting presentation mode.");
      return;
    }
    resetRunState();
    setMode("demo");
    setRunning(true);
    setLiveStatus("idle");
    setStatus(currentSlide ? `Demo running on slide ${currentSlide.slideNumber}.` : "Demo transcript is running.");
  }

  function stopDemo() {
    setRunning(false);
    if (mode === "demo") {
      setMode("idle");
    }
    setStatus("Demo paused.");
  }

  function resetDemo() {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    resetRunState();
    setSlides([]);
    setPreparedQuestions([]);
    setQuestionSource(undefined);
    setQuestionCacheHit(false);
    setCurrentSlideIndex(0);
    setUploadedFilename(undefined);
    stopLiveSpeech("Ready for fake transcript mode.");
    setMode("idle");
    setStatus("Ready for fake transcript mode.");
  }

  function openDrawer() {
    setDrawerOpen(true);
    setUnseenCount(0);
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

  async function handleFinalize() {
    if (!sessionId) {
      setStatus("Start a session before finalizing the grade.");
      return;
    }

    try {
      const evaluation = await finalizeSession(sessionId);
      setFinalEvaluation(evaluation);
      setDrawerOpen(true);
      setStatus(`Final grade ready: ${evaluation.overallGrade} (${evaluation.numericScore}).`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to finalize presentation.");
    }
  }

  useEffect(() => {
    if (!running) {
      return;
    }

    timerRef.current = setTimeout(() => {
      void sendNextChunk();
    }, transcript.length === 0 ? 250 : 4500);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [running, chunkIndex, transcript.length]);

  useEffect(() => () => stopLiveSpeech("Live microphone stopped."), []);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Faculty AI</p>
          <h1>Student presentation mode</h1>
        </div>
        <p>{status}</p>
      </header>

      <div className="workspace">
        <div className="left-rail">
          <section className="setup-panel">
            <div>
              <p className="eyebrow">Professor Rubric</p>
              <h2>{professorConfig?.assignmentName ?? "Project Presentation"}</h2>
            </div>
            <p className="muted">
              {(professorConfig?.rubric ?? projectContext.rubric).join(", ")}
            </p>
            {questionSource ? (
              <p className="muted">
                Question source: {questionSource}{questionCacheHit ? " (cache hit)" : ""}
              </p>
            ) : null}
            <p className="muted">
              {mode === "live"
                ? "Live microphone mode is active."
                : mode === "demo"
                  ? "Fake demo mode is active."
                  : "Choose live microphone or fake demo mode."}
            </p>
          </section>
          <PresentationUpload disabled={busy} filename={uploadedFilename} onUpload={(file) => void handleUpload(file)} />
          <SessionControls
            canFinalize={Boolean(sessionId && transcript.length > 0)}
            disabled={busy}
            liveConnected={liveConnected}
            liveConnecting={liveConnecting}
            liveStatus={liveStatus}
            running={running}
            sessionId={sessionId}
            onStart={startDemo}
            onStop={stopDemo}
            onReset={resetDemo}
            onNextChunk={() => void sendNextChunk()}
            onStartLive={() => void startLiveSpeech()}
            onStopLive={() => stopLiveSpeech()}
            onFinalize={() => void handleFinalize()}
          />
        </div>

        <div className="main-stage">
          <SlideTracker
            currentSlideIndex={currentSlideIndex}
            preparedQuestions={preparedQuestions}
            slides={slides}
            onPrevious={() => setCurrentSlideIndex((index) => Math.max(0, index - 1))}
            onNext={() => setCurrentSlideIndex((index) => Math.min(slides.length - 1, index + 1))}
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

      <FeedbackDrawer feedback={feedback} latestFeedback={latestFeedback} open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      {finalEvaluation ? (
        <aside className="feedback-drawer open final-evaluation" aria-hidden={false}>
          <div className="drawer-header">
            <div>
              <p className="eyebrow">Final Evaluation</p>
              <h2>
                {finalEvaluation.projectTitle}: {finalEvaluation.overallGrade} ({finalEvaluation.numericScore})
              </h2>
            </div>
            <button onClick={() => setFinalEvaluation(undefined)} type="button">
              Close
            </button>
          </div>
          <p>{finalEvaluation.summary}</p>
          <div className="feedback-list">
            {finalEvaluation.rubricScores.map((item) => (
              <article className="feedback-card question" key={item.criterion}>
                <div className="feedback-meta">
                  <span>{item.criterion}</span>
                  <span>{item.score}/5</span>
                </div>
                <small>{item.justification}</small>
              </article>
            ))}
          </div>
        </aside>
      ) : null}
      <FacultyAlert latestFeedback={latestFeedback} unseenCount={unseenCount} onOpen={openDrawer} />
    </main>
  );
}
