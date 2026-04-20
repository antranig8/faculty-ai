"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { FacultyAlert } from "@/components/FacultyAlert";
import { FeedbackDrawer } from "@/components/FeedbackDrawer";
import { PresentationUpload } from "@/components/PresentationUpload";
import { SessionControls } from "@/components/SessionControls";
import { SlideTracker } from "@/components/SlideTracker";
import { TranscriptPanel } from "@/components/TranscriptPanel";
import { analyzeChunk, getProfessorConfig, startSession, uploadPresentation } from "@/lib/api";
import { demoTranscriptChunks } from "@/lib/demoTranscript";
import type { FeedbackItem, PreparedQuestion, ProfessorConfig, ProjectContext, Slide } from "@/lib/types";

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
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [transcript, setTranscript] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [activeChunk, setActiveChunk] = useState("");
  const [chunkIndex, setChunkIndex] = useState(0);
  const [running, setRunning] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [unseenCount, setUnseenCount] = useState(0);
  const [status, setStatus] = useState("Ready for fake transcript mode.");
  const [busy, setBusy] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const latestFeedback = feedback[feedback.length - 1];
  const recentFeedback = useMemo(() => feedback.slice(-5).map((item) => item.message), [feedback]);
  const currentSlide = slides[currentSlideIndex];

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
    const id = await startSession(projectContext);
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
      const nextTranscript = [...transcript, nextChunk];
      setTranscript(nextTranscript);
      setActiveChunk(nextChunk);
      setChunkIndex((current) => current + 1);

      const result = await analyzeChunk({
        sessionId: id,
        transcriptChunk: nextChunk,
        recentTranscript: nextTranscript.slice(-4),
        recentFeedback,
        projectContext,
        currentSlide,
        preparedQuestions,
      });

      if (result.trigger && result.feedback) {
        setFeedback((current) => [...current, result.feedback as FeedbackItem]);
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

  function startDemo() {
    if (slides.length === 0) {
      setStatus("Upload a .pptx before starting presentation mode.");
      return;
    }
    setRunning(true);
    setStatus(currentSlide ? `Demo running on slide ${currentSlide.slideNumber}.` : "Demo transcript is running.");
  }

  function stopDemo() {
    setRunning(false);
    setStatus("Demo paused.");
  }

  function resetDemo() {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    setSessionId(undefined);
    setTranscript([]);
    setFeedback([]);
    setSlides([]);
    setPreparedQuestions([]);
    setCurrentSlideIndex(0);
    setUploadedFilename(undefined);
    setActiveChunk("");
    setChunkIndex(0);
    setRunning(false);
    setDrawerOpen(false);
    setUnseenCount(0);
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
      setCurrentSlideIndex(0);
      setUploadedFilename(file.name);
      setStatus(`Prepared ${result.preparedQuestions.length} faculty questions from ${result.slides.length} slides.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to upload presentation.");
    } finally {
      setBusy(false);
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
          </section>
          <PresentationUpload disabled={busy} filename={uploadedFilename} onUpload={(file) => void handleUpload(file)} />
          <SessionControls
            disabled={busy}
            running={running}
            sessionId={sessionId}
            onStart={startDemo}
            onStop={stopDemo}
            onReset={resetDemo}
            onNextChunk={() => void sendNextChunk()}
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
          <TranscriptPanel activeChunk={activeChunk} transcript={transcript} />
        </div>
      </div>

      <FeedbackDrawer feedback={feedback} open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <FacultyAlert latestFeedback={latestFeedback} unseenCount={unseenCount} onOpen={openDrawer} />
    </main>
  );
}
