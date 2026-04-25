# FacultyAI Live Feedback

## Project Summary

FacultyAI is a live presentation critique assistant for ENES 104 style presentations.

It lets a professor define the assignment framing and rubric, lets a student upload a `.pptx` deck, listens to the student's live microphone audio, and surfaces selective faculty-style questions when the spoken presentation leaves an important gap.

The current version is not a generic presentation helper. It is designed to behave like a skeptical but fair faculty examiner that only interrupts when there is a concrete academic reason.

## Current Goal

The project currently aims to support live rehearsal for slide-based presentations by combining:

- professor rubric and assignment context
- uploaded slide content
- prepared slide-aware faculty questions
- live transcript chunks
- selective interruption logic

The intended output is the kind of question a faculty member or executive audience member might actually ask during a presentation, such as:

- "What evidence shows that this is a real problem for your target users?"
- "Why was this the right approach instead of a simpler alternative?"
- "What metric supports that claim?"
- "What exactly is the AI deciding here?"

The system should avoid filler, duplication, and over-triggering.

## What Exists Now

### User-Facing Flow

1. A professor configures the course framing, rubric, and questioning style at `/professor`.
2. A student opens `/present`.
3. The student uploads a `.pptx` deck.
4. The backend parses slide text and prepares likely faculty concerns for the deck.
5. The student starts live microphone mode.
6. FacultyAI streams audio to the backend speech proxy, receives transcript events, analyzes transcript chunks, and raises faculty questions when warranted.
7. The presenter can mark a question addressed or reopen it later.

### Current Capabilities

- professor-owned rubric and assignment setup
- `.pptx` upload and slide text extraction
- slide-aware prepared faculty question generation
- prepared-question caching
- live microphone transcription through Deepgram
- automatic slide inference from transcript content
- manual slide override in the UI
- selective faculty-question triggering
- cooldown and dedupe logic
- one-question-per-slide enforcement
- question resolution and reopen flow
- faculty voice playback through Deepgram TTS with HTTP fallback
- SQLite persistence for professor config, session state, feedback, and prepared-question cache

### What Does Not Exist

- demo mode
- standalone results/history page
- final grading flow
- multi-user collaboration
- deck viewer with rendered slides inside the app

`/results` currently redirects back to `/present`.

## Current Stack

### Frontend

- Next.js 16
- React 19
- TypeScript

Frontend responsibilities:

- access-code gate when enabled
- professor setup page
- presentation cockpit UI
- deck upload
- slide tracker
- live transcript display
- faculty alert and feedback drawer
- mic/session controls
- resolution controls for faculty questions

### Backend

- FastAPI
- Python
- SQLite

Backend responsibilities:

- load professor config and prompt assets
- parse uploaded `.pptx` files
- prepare slide-aware questions
- receive transcript analysis requests
- infer slide position from transcript content
- trigger or suppress faculty feedback
- proxy live Deepgram speech streams
- proxy/synthesize Deepgram TTS
- persist app state and cache

### Providers

- Deepgram for live speech-to-text and TTS
- Groq optionally for prepared-question generation and live faculty reasoning
- deterministic heuristic fallback when Groq is unavailable

## Architecture

## High-Level Flow

1. The professor configuration is loaded from persisted backend state.
2. The student uploads a `.pptx`.
3. The backend extracts slide text and prepares a question set for the deck.
4. The frontend starts a presentation session and opens a live speech WebSocket to the backend.
5. The backend proxies the audio stream to Deepgram.
6. Final transcript events are chunked and analyzed against:
   - recent transcript
   - recent feedback
   - current slide
   - all slides
   - prepared questions
   - professor-owned assignment context
7. The backend either:
   - does nothing
   - auto-resolves a previously asked question
   - emits one faculty question
8. The frontend shows the alert, opens the drawer, and optionally speaks the question aloud.

## Decision Model

The live decision model is now closer to:

```text
Professor rubric + prepared slide concerns + inferred current slide + recent transcript
= decide whether a faculty question should be asked now
```

The project no longer relies on a generic "ask anything interesting" model. Prepared slide-aware concerns are the primary source material, with heuristic and optional LLM logic deciding whether the moment is strong enough to interrupt.

## Repository Layout

```text
FacultyAI/
|- backend/
|  |- app/
|  |  |- main.py
|  |  |- config.py
|  |  |- state.py
|  |  |- models/
|  |  |- prompts/
|  |  |- routes/
|  |  `- services/
|  |- requirements.txt
|  `- README.md
|- frontend/
|  |- app/
|  |- components/
|  |- lib/
|  |- package.json
|  `- README.md
|- docs/
|  |- faculty_ai_live_feedback_README.md
|  |- slide_aware_faculty_examiner_direction.md
|  `- speech_provider_split.md
|- faculty_ai.db
|- package.json
`- README.md
```

## Important Routes

### Frontend Routes

- `/`
- `/access`
- `/professor`
- `/present`
- `/results` redirected to `/present`

### Backend Routes

- `GET /`
- `GET /health`
- `POST /session/start`
- `GET /session/{session_id}/feedback`
- `PATCH /session/{session_id}/feedback/{created_at}/resolution`
- `POST /analyze-chunk`
- `POST /presentation/upload`
- `POST /presentation/prepare`
- `GET /professor/config`
- `POST /professor/config`
- `POST /speech/{provider_name}/session`
- `GET /speech/deepgram/tts/preview`
- `POST /speech/deepgram/tts`
- `WS /speech/deepgram/proxy`
- `WS /speech/deepgram/tts/stream`

## Persistence

State is persisted in `faculty_ai.db` at the repository root.

Persisted data currently includes:

- professor config
- session payloads
- feedback history
- prepared-question cache

## Configuration

Important environment variables:

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_FACULTY_AI_APP_API_KEY`
- `FACULTY_AI_ACCESS_CODE`
- `FACULTY_AI_ALLOWED_ORIGINS`
- `FACULTY_AI_APP_API_KEY`
- `DEEPGRAM_API_KEY`
- `DEEPGRAM_MODEL`
- `DEEPGRAM_LANGUAGE`
- `FACULTY_AI_SPEECH_PROVIDER`
- `GROQ_API_KEY`
- `FACULTY_AI_LLM_PROVIDER`
- `FACULTY_AI_LLM_MODEL`

Localhost backend access is allowed without `FACULTY_AI_APP_API_KEY`. Non-local HTTP and WebSocket access requires the key.

## How To Run

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/`.

You can also use the root scripts:

```powershell
npm run backend:dev
npm run frontend:dev
```

## Product Rules

The current product should follow these rules:

- interrupt only when there is a specific faculty reason
- prefer prepared slide-aware concerns over generic questioning
- avoid repeated questions
- do not ask multiple questions on the same slide
- do not interrupt immediately on slide arrival
- give the presenter time to answer before asking another question
- treat transcript content as timing evidence, not a reason to freestyle harsher questions

## Current Gaps

The strongest missing pieces in the current build are:

- a real session history/results page
- clearer visibility into why a question triggered or auto-resolved
- stronger observability for provider/model status
- richer review of past rehearsals after the live session ends

## Related Docs

- `README.md`: current project overview and run instructions
- `backend/README.md`: backend routes, config, and persistence
- `frontend/README.md`: frontend routes and current behavior
- `docs/slide_aware_faculty_examiner_direction.md`: design intent
- `docs/speech_provider_split.md`: provider separation rationale
