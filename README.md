# Faculty-AI

A live rehearsal tool for academic presentations. Faculty-AI listens while you present, follows along in your slides, and asks the kind of pointed question a faculty member would: when you make a vague claim, skip a justification, or leave an idea underdeveloped.

## Features

- **Professor-defined examiner.** The instructor sets the rubric, assignment context, and questioning style once; every rehearsal uses it.
- **Slide-aware preparation.** Upload a `.pptx` and Faculty-AI classifies each slide and prepares likely questions before you start.
- **Live listening.** Microphone audio is transcribed in real time, and the active slide is inferred from what you say (with manual override).
- **Well-timed interruptions.** Questions are held until you've finished setting context, with cooldowns and a one-question-per-slide rule so it never piles on.
- **Answer evaluation.** Your response is judged `strong`, `partial`, or `weak`; a partial answer gets at most one follow-up.
- **Spoken questions.** Questions are read aloud, and you can ask Faculty-AI to repeat or rephrase them.
- **Per-student targeting.** On individual slides it picks up details like a student's major and tailors later questions to them.
- **Works offline from LLMs.** Every decision has a deterministic fallback; an LLM (Groq) is optional.

## How It Works

```text
browser mic ──▶ FastAPI ──▶ Deepgram speech-to-text
                   │
                   ▼
   slides + rubric + transcript ──▶ decision engine ──▶ question ──▶ Deepgram text-to-speech
                                    (heuristic or Groq)
```

On each transcript chunk, the engine decides whether to ask a prepared question, ask a freeform one, follow up, wait, or stay quiet. See [How Faculty-AI Thinks](docs/how-it-thinks.md) for the full decision model.

| Layer | Stack |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript |
| Backend | FastAPI, Python, SQLite |
| Speech | Deepgram (live transcription and TTS) |
| LLM (optional) | Groq (Qwen 3) |

## Getting Started

**Requirements:** Python 3.10+, Node.js 20+, and a [Deepgram](https://deepgram.com) API key for live audio. A [Groq](https://groq.com) key is optional.

1. Configure the environment:

   ```powershell
   Copy-Item .env.example .env
   ```

   Then fill in `DEEPGRAM_API_KEY` (and optionally `GROQ_API_KEY` with `FACULTY_AI_LLM_PROVIDER=groq`).

2. Start the backend:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

3. Start the frontend in a second terminal:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Open <http://localhost:3000>.

## Using It

1. Go to **/professor** and save the course rubric and assignment context.
2. Go to **/present** and upload your `.pptx`.
3. Start the microphone and present normally.
4. Answer questions as they come. Say "repeat that" or ask for a rephrase if needed.
5. Review, resolve, or reopen questions in the feedback drawer.

## Configuration

All variables live in `.env` at the repo root (see [`.env.example`](.env.example)).

| Variable | Default | Purpose |
|---|---|---|
| `DEEPGRAM_API_KEY` | none | Live transcription and spoken questions |
| `DEEPGRAM_MODEL` | `flux-general-en` | Speech-to-text model |
| `DEEPGRAM_LANGUAGE` | `en-US` | Transcription language (non-Flux models) |
| `GROQ_API_KEY` | none | Enables LLM features and question rephrasing |
| `FACULTY_AI_LLM_PROVIDER` | `heuristic` | Set to `groq` to use the LLM for question selection |
| `FACULTY_AI_LLM_MODEL` | `qwen/qwen3-32b` | Main Groq model |
| `FACULTY_AI_REPHRASE_MODEL` | `qwen/qwen3-8b` | Lighter model for rephrasing |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend URL used by the frontend |
| `FACULTY_AI_ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Backend CORS allowlist |
| `FACULTY_AI_APP_API_KEY` | none | Required for non-localhost backend access |
| `NEXT_PUBLIC_FACULTY_AI_APP_API_KEY` | none | The key the frontend sends to the backend |
| `FACULTY_AI_ACCESS_CODE` | none | Puts every frontend page behind an access code |

### Security notes

- The backend accepts unauthenticated requests only from localhost. Any other client must send `x-facultyai-key` (or `?key=` on WebSockets).
- `NEXT_PUBLIC_*` values are compiled into browser JavaScript, so `NEXT_PUBLIC_FACULTY_AI_APP_API_KEY` is visible to anyone who can load the frontend. It deters casual use of a deployed backend but is not a secret.
- Provider keys (`DEEPGRAM_API_KEY`, `GROQ_API_KEY`) stay on the backend; audio and speech are proxied so the browser never sees them.

## Project Structure

```text
backend/
  app/
    routes/        HTTP and WebSocket endpoints
    services/      decision engine, slide parsing, answer evaluation, eval runner
    prompts/       LLM prompts and the default professor rubric
  eval_scenarios/  sample deck, replay scenarios, and reports
frontend/
  app/             pages: home, /professor, /present, /access
  components/      presentation cockpit UI
  lib/             API client and shared types
docs/
  how-it-thinks.md   decision model in plain English
  eval-harness.md    offline replay for tuning without a microphone
```

App state (professor config, sessions, prepared-question cache) is stored in `faculty_ai.db` at the repo root, which is created on first run and git-ignored.
