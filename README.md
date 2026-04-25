# FacultyAI

FacultyAI is a live presentation critique assistant for ENES 104 style demos. Professors define the assignment context and rubric, students upload a `.pptx`, and the app listens for spoken presentation content to surface selective faculty-style questions during rehearsal.

## Current Build

- `frontend/`: Next.js 16 + React 19 presentation UI
- `backend/`: FastAPI service for upload, slide prep, transcript analysis, speech proxying, and TTS
- Repo-root `.env` loading for backend and frontend configuration
- Professor setup page at `/professor`
- Presentation cockpit at `/present`
- Optional access-code gate across frontend routes via `FACULTY_AI_ACCESS_CODE`
- `.pptx` upload with slide parsing and slide-aware prepared questions
- slide category and lightweight slide author inference
- Automatic slide inference from transcript content, with manual slide override
- Live microphone transcription through the backend Deepgram proxy
- Deepgram-backed faculty question voice playback with HTTP fallback
- queued questions when timing is not right for immediate interruption
- answer evaluation with weak/partial/strong outcomes and one follow-up max
- timing-aware delivery based on time spent on the active slide
- Faculty question resolution and reopen flow
- SQLite persistence for professor config, sessions, and prepared-question cache in `faculty_ai.db`
- lightweight student-profile memory for major / interest cues on individual reflection slides

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

Without `GROQ_API_KEY`, the app falls back to deterministic heuristic question generation and live feedback logic.

## Workflow

1. Open `/professor` and save the course rubric and assignment context.
2. Open `/present`.
3. Upload a `.pptx` deck.
4. Start live microphone mode.
5. Present normally while FacultyAI tracks transcript context and current slide.
6. Review or resolve triggered faculty questions in the drawer.

`/results` currently redirects back to `/present`; there is no standalone results page in the current build.

## Notes

- The backend allows localhost access without `x-facultyai-key`.
- Non-local requests must send `x-facultyai-key`, and the speech proxies also accept `?key=...`.
- Prepared questions are cached by project context + slide content.
- The live runtime is hybrid: prepared concerns are anchors, but deterministic and optional LLM paths can choose a better freeform question when the moment supports it.

## Docs

Use the docs in `docs/` like this:

- `docs/faculty_ai_how_it_thinks.md`
  - plain-English explanation of how the runtime listens, waits, chooses, and asks questions
- `docs/faculty_ai_interaction_model.md`
  - current architecture direction: prepared questions as anchors, not shackles
- `docs/faculty_ai_live_feedback_README.md`
  - current-state product and architecture summary
- `docs/faculty_ai_eval_harness.md`
  - how to replay saved scenarios offline
- `docs/what_i_need_from_you_for_eval.md`
  - concise handoff checklist for preparing eval scenarios
- `docs/faculty_ai_POTENTIAL.md`
  - roadmap / next-step priorities
- `docs/slide_aware_faculty_examiner_direction.md`
  - earlier design-direction document; useful for historical context, but not the main current-state source
