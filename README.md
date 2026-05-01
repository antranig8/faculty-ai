# FacultyAI

FacultyAI is a live rehearsal system for academic presentations. It lets a professor define the rubric, prepares slide-aware questions from a `.pptx`, listens to the presentation in real time, and interrupts selectively with faculty-style questions when the speaker leaves weak reasoning, vague claims, or missing evidence on the table.

## What It Does

- Builds a professor-defined questioning style from the assignment context, rubric, and expectations saved in `/professor`
- Parses presentation decks and prepares slide-specific faculty questions before rehearsal starts
- Tracks where the presenter likely is in the deck from transcript content, with manual slide control available when needed
- Listens to live microphone audio through the backend speech proxy and analyzes transcript chunks during the run
- Times interruptions instead of firing constantly, including queuing questions until the moment is better
- Evaluates presenter answers as `weak`, `partial`, or `strong`, and can queue one follow-up when a response only partly addresses the concern
- Speaks faculty questions out loud with Deepgram TTS, with fallback HTTP synthesis if streaming TTS is unavailable
- Handles "repeat that" and "rephrase the question" moments during live rehearsal
- Builds lightweight student profiles from what speakers say on individual reflection slides, including major and interest cues, so later questions can target the right student
- Persists professor config, sessions, feedback history, and prepared-question cache in SQLite

## Main Surfaces

- `/`: home screen
- `/professor`: rubric, assignment context, and questioning setup
- `/present`: live presentation cockpit with upload, transcript, slide tracking, and faculty feedback drawer
- `/results`: currently redirects back to `/present`
- optional access-code gate across frontend routes via `FACULTY_AI_ACCESS_CODE`

## Run

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

You can also use the root scripts:

```powershell
npm run backend:dev
npm run frontend:dev
```

Open `http://localhost:3000/`.

## Environment

Common variables:

- `NEXT_PUBLIC_API_BASE_URL`: frontend API base, defaults to `http://localhost:8000`
- `FACULTY_AI_ACCESS_CODE`: enables the frontend access page and signed access cookie flow
- `FACULTY_AI_ALLOWED_ORIGINS`: backend CORS origins, defaults to `http://localhost:3000,http://127.0.0.1:3000`
- `FACULTY_AI_APP_API_KEY`: required for non-local backend HTTP/WebSocket access

Speech and LLM variables:

- `DEEPGRAM_API_KEY`: enables live transcription proxy and Deepgram TTS
- `DEEPGRAM_MODEL`: defaults to `flux-general-en`
- `DEEPGRAM_LANGUAGE`: defaults to `en-US`
- `FACULTY_AI_SPEECH_PROVIDER`: currently defaults to `deepgram`
- `GROQ_API_KEY`: enables Groq-backed prepared-question generation and live reasoning
- `FACULTY_AI_LLM_PROVIDER`: defaults to `heuristic`
- `FACULTY_AI_LLM_MODEL`: defaults to `qwen/qwen3-32b`
- `FACULTY_AI_REPHRASE_MODEL`: optional lighter Groq model for question simplification, defaults to `qwen/qwen3-8b`

Without `GROQ_API_KEY`, the app falls back to deterministic heuristic question generation and live feedback logic.

## Workflow

1. Open `/professor` and save the course rubric and assignment context.
2. Open `/present`.
3. Upload a `.pptx` deck.
4. Start live microphone mode.
5. Present normally while FacultyAI tracks transcript context, watches for slide changes, and decides whether to ask now or wait.
6. Answer live faculty questions, repeat or rephrase them if needed, and let the system judge whether the response actually closed the issue.
7. Review, resolve, or reopen faculty questions in the feedback drawer.

## Notes

- The backend allows localhost access without `x-facultyai-key`.
- Non-local requests must send `x-facultyai-key`, and the speech proxies also accept `?key=...`.
- Prepared questions are cached by project context and slide content.
- The runtime is hybrid: prepared questions anchor the session, but live heuristics and optional Groq-backed reasoning can choose a better question when the transcript supports it.
