# Project Update

Last updated: April 20, 2026

## Current State

FacultyAI is now a live presentation critique prototype with:

- `.pptx` upload and slide text extraction
- prepared slide-specific faculty concerns
- live microphone transcription through Deepgram
- transcript-to-slide inference from spoken content
- structured faculty-question reasoning using slide concerns plus live transcript evidence
- SQLite persistence for sessions, preparation cache, and final results
- end-of-presentation grading against the professor rubric template

This is no longer just a fake transcript demo. The app has a real live-audio path, but the live path is still being tuned for stability, transcript quality, and LLM cost/rate-limit control.

## Architecture Snapshot

Frontend:

- Next.js app in `frontend/`
- presenter workflow in `frontend/app/present/page.tsx`
- live mic capture uses browser PCM audio -> backend WebSocket proxy
- faculty drawer auto-opens when a question triggers

Backend:

- FastAPI app in `backend/app/`
- Deepgram speech proxy in `backend/app/routes/speech.py`
- live analysis in `backend/app/routes/analyze.py`
- question preparation in `backend/app/services/presentation_preparer.py`
- structured faculty reasoning in `backend/app/services/faculty_brain.py`
- transcript evidence extraction in `backend/app/services/transcript_evidence.py`
- final grading in `backend/app/services/final_evaluator.py`
- persistence in `backend/app/state.py`

## Working Now

- Root `.env` is the active config source.
- `DEEPGRAM_MODEL=nova-3` is the recommended stable demo setting right now.
- Live microphone mode works through the backend speech proxy.
- Prepared questions are generated from uploaded slides and cached.
- Current slide can be inferred automatically from the transcript.
- Faculty questions are capped to one per slide per session.
- Duplicate transcript chunks and duplicate faculty questions are suppressed.
- Final grading and results persistence work.

## Known Limits

- Groq still rate-limits on the free/on-demand tier if prompts get too large or too frequent.
- Live transcript quality still depends heavily on microphone quality, noise, and speaking style.
- Slide inference is heuristic, so sparse slides or vague spoken wording can still cause drift.
- The app still mixes deterministic logic and LLM logic; the balance is improving, but it is not fully production-stable.
- There is no full answer-resolution lifecycle yet for live faculty questions.

## Current LLM Strategy

The repo is currently configured around:

- Groq provider
- `qwen/qwen3-32b` default model
- reduced token budgets for live faculty decisions
- deterministic prepared-question logic first
- LLM backoff after rate-limit events

This means live questioning should continue functioning even when Groq is temporarily unavailable, but the quality may fall back toward deterministic logic.

## Recommended Demo Configuration

Use these values in `.env`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

DEEPGRAM_API_KEY=
GROQ_API_KEY=

FACULTY_AI_SPEECH_PROVIDER=deepgram
FACULTY_AI_LLM_PROVIDER=groq
FACULTY_AI_LLM_MODEL=qwen/qwen3-32b

DEEPGRAM_MODEL=nova-3
DEEPGRAM_LANGUAGE=en-US
```

## Immediate Next Steps

1. Live-test the Nova-3 path end to end and confirm transcript stability.
2. Continue shrinking live LLM token usage if Groq TPM limits still hit too often.
3. Add answer-resolution tracking so a faculty question can be marked resolved and visually dismissed after the presenter addresses it.
4. Keep manual slide controls only as a fallback; rely primarily on transcript-based slide inference.

## Product Direction

Short-term goal:

- stable ENES 104 demo where the AI listens live, asks selective faculty questions, and produces a rubric-based final grade

Long-term goal:

- a more agent-like live faculty examiner, likely returning to Flux later if the product evolves into real spoken back-and-forth with TTS
