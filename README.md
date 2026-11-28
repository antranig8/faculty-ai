# Faculty-AI

A local rehearsal tool for academic presentations. Faculty-AI listens while you present, tracks your slides, and asks faculty-style questions when a claim needs evidence or an idea needs more explanation. The app and database run on your computer. Live transcription and voice use Deepgram over the internet.

## Features

- **Professor-defined examiner.** The instructor sets the rubric, assignment context, and questioning style for rehearsals.
- **Slide-aware preparation.** Upload a `.pptx` and Faculty-AI classifies each slide and prepares likely questions before you start.
- **Live listening.** Microphone audio is transcribed in real time, and the active slide is inferred from what you say (with manual override).
- **Well-timed interruptions.** Questions are held until you've finished setting context, with cooldowns and one initial question per slide.
- **Answer evaluation.** Your response is judged `strong`, `partial`, or `weak`; a partial answer gets at most one follow-up.
- **Spoken questions.** Questions are read aloud, and you can ask Faculty-AI to repeat or rephrase them.
- **Per-student targeting.** On individual slides it picks up details like a student's major and tailors later questions to them.
- **Works without an LLM.** Heuristic mode uses Deepgram for live speech. You can also replay a transcript offline.

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
| LLM (optional) | Groq (GPT-OSS for question selection, Qwen for rephrasing) |

## Run locally

Use Python 3.11 or later and Node.js 20.9 or later. Live audio requires a Deepgram API key. A Groq API key enables optional model-backed features. [Deepgram](https://deepgram.com) · [Groq](https://groq.com)

1. From the repository root, create the configuration file if needed.

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

   Set `DEEPGRAM_API_KEY` in the root `.env`. For Groq question preparation and live selection, also set `GROQ_API_KEY` and `FACULTY_AI_LLM_PROVIDER=groq`. If an existing `.env` still names `qwen/qwen3-32b` or `qwen/qwen3-8b`, update the model values to the defaults in the configuration table.

2. Install the backend and frontend dependencies.

   ```powershell
   python -m venv backend/.venv
   .\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\backend\.venv\Scripts\python.exe -m pip install --upgrade -r backend\requirements.txt
   npm --prefix frontend ci
   ```

3. Start both services in the same terminal.

   ```powershell
   npm run dev
   ```

4. Open <http://127.0.0.1:3000>. Press Ctrl+C in the terminal to stop both services. The backend serves a [health check](http://127.0.0.1:8000/health) and [API docs](http://127.0.0.1:8000/docs).

The launcher binds both services to loopback, points the browser at the local backend, and opens the app without an access code. The optional access code still applies when the frontend is started separately. Configure Groq and Deepgram in the root `.env`.

## Using It

1. Open **Professor** and save the course rubric and assignment context.
2. Open **Present** and drop your `.pptx` onto **Upload your deck**, or use **Choose a .pptx**. The [bundled sample deck](backend/eval_scenarios/group2_example_deck.pptx) works for a smoke test.
3. Start the microphone and present normally.
4. Answer questions as they come. Say "repeat that" or ask for a rephrase if needed.
5. Read and respond to questions as they appear beside the professor cutout. Open **Feedback** to review, resolve, or reopen questions. A partial answer can queue one follow-up on the same slide. Asking “Does that answer your question?” leaves the question open unless the answer meets the resolution criteria.

Open **Transcript** for the full transcript or **Session** for deck replacement, rubric details, prepared concerns, and diagnostics.

In **Manual lock**, moving to a later slide marks the on-screen faculty question addressed. Open **Results** to review the latest rehearsal started in this browser, including open and addressed questions. Leaving **Present** stops the microphone.

## Configuration

Use the root [`.env`](.env.example) for local setup. Restart both services after editing it. When you start the frontend separately, Next.js uses the root file as a fallback to shell variables and its own environment files such as `frontend/.env.local`. Set `NEXT_PUBLIC_*` variables before building a production frontend.

| Variable | Default | Purpose |
|---|---|---|
| `DEEPGRAM_API_KEY` | none | Live transcription and spoken questions |
| `DEEPGRAM_MODEL` | `flux-general-en` | Speech-to-text model |
| `DEEPGRAM_LANGUAGE` | `en-US` | Transcription language (non-Flux models) |
| `GROQ_API_KEY` | none | Enables LLM features and question rephrasing |
| `FACULTY_AI_LLM_PROVIDER` | `heuristic` | Set to `groq` to use the LLM for question selection |
| `FACULTY_AI_LLM_MODEL` | `openai/gpt-oss-120b` | Groq model for preparation and live question selection |
| `FACULTY_AI_REPHRASE_MODEL` | `qwen/qwen3.8-27b` | Groq model for rephrasing |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend URL used by the frontend |
| `FACULTY_AI_ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Backend CORS allowlist |
| `FACULTY_AI_APP_API_KEY` | none | Required for non-localhost backend access |
| `NEXT_PUBLIC_FACULTY_AI_APP_API_KEY` | none | The key the frontend sends to the backend |
| `FACULTY_AI_ACCESS_CODE` | none | Optional access prompt for a separately started frontend |
| `FACULTY_AI_DB_PATH` | `faculty_ai.db` at the repo root | Optional absolute path to a writable SQLite database file |

### Security notes

- The backend exposes `/` and `/health` for health checks. Other endpoints require `x-facultyai-key` from non-local clients. WebSocket clients can also use `?key=`.
- `NEXT_PUBLIC_*` values are compiled into browser JavaScript, so `NEXT_PUBLIC_FACULTY_AI_APP_API_KEY` is visible to anyone who can load the frontend. It deters casual use of a deployed backend but is not a secret.
- Provider keys (`DEEPGRAM_API_KEY`, `GROQ_API_KEY`) stay on the backend. Audio is sent to Deepgram. With Groq enabled, the backend can send slide and transcript text to Groq.
- The access code is shared across the app. Deploy this version in a trusted environment. Professor/student permissions, session ownership, and retention policies require application-level controls.

## Verification

GitHub Actions runs the backend regression tests and frontend type check and build on pushes and pull requests. Run these commands from the repository root to verify the app and replay the sample offline.

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
Push-Location backend
.\.venv\Scripts\python.exe -m unittest discover -s tests
$previousProvider = $env:FACULTY_AI_LLM_PROVIDER
$env:FACULTY_AI_LLM_PROVIDER = 'heuristic'
.\.venv\Scripts\python.exe -m app.services.eval_runner eval_scenarios\faculty_ai_group2_example_scenario.json
$env:FACULTY_AI_LLM_PROVIDER = $previousProvider
Pop-Location
```

See the [replay harness](docs/eval-harness.md) to exercise the decision engine offline. The [backend](backend/README.md) and [frontend](frontend/README.md) also have separate startup commands for debugging.

## Project Structure

```text
backend/
  app/
    routes/        HTTP and WebSocket endpoints
    services/      decision engine, slide parsing, answer evaluation, eval runner
    prompts/       LLM prompts and the default professor rubric
  eval_scenarios/  sample deck, replay scenarios, and reports
  tests/           backend regression tests
frontend/
  app/             pages: home, /professor, /present, /access
  components/      presentation cockpit UI
  lib/             API client and shared types
docs/
  how-it-thinks.md   decision model in plain English
  eval-harness.md    offline replay for tuning without a microphone
scripts/
  run_local.py     starts and stops both local services
```

By default the app stores professor settings, sessions, and prepared questions in the git-ignored `faculty_ai.db` at the repo root.
