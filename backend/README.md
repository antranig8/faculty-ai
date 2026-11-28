# Faculty-AI Backend

FastAPI service that parses decks, prepares questions, runs the live decision engine, and proxies Deepgram speech. Use `npm run dev` from the repository root to start both services. To run just the backend for debugging, use Python 3.11 or later and run these commands from this directory.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive API docs are served at <http://127.0.0.1:8000/docs> while the server is running.

Run the backend regression suite with `python -m unittest discover -s tests` from `backend/`. The suite uses temporary SQLite storage and does not contact speech or LLM providers.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` / `POST` | `/professor/config` | Read or save the rubric and assignment context |
| `POST` | `/presentation/upload` | Upload a `.pptx` and get slides plus prepared questions |
| `POST` | `/presentation/prepare` | Same, from a plain-text slide outline |
| `POST` | `/session/start` | Start a rehearsal session |
| `POST` | `/analyze-chunk` | Run the decision engine on a transcript chunk |
| `GET` | `/session/{id}/feedback` | List questions asked in a session |
| `PATCH` | `/session/{id}/feedback/{created_at}/resolution` | Resolve or reopen a question |
| `POST` | `/speech/rephrase-question` | Simplify a question (requires Groq) |
| `GET` | `/speech/deepgram/tts/preview` | Report whether TTS is configured |
| `POST` | `/speech/deepgram/tts` | Synthesize a question to MP3 |
| `WS` | `/speech/deepgram/proxy` | Live transcription proxy |
| `WS` | `/speech/deepgram/tts/stream` | Streaming TTS proxy |

## Layout

- `app/routes/`: HTTP and WebSocket endpoints
- `app/services/`: decision engine (`faculty_brain.py`, `feedback_engine.py`), deck parsing and question preparation, answer evaluation, student profiles, and the eval runner
- `app/prompts/`: LLM prompts and the default professor rubric
- `app/state.py`: in-memory state backed by SQLite (`faculty_ai.db` at the repo root)
- `eval_scenarios/` contains replay scenarios and a sample report. The deck is shared with the main README. [Eval harness](../docs/eval-harness.md)
