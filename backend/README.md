# FacultyAI Backend

FastAPI service for presentation upload, slide-aware question preparation, transcript analysis, speech proxying, TTS, and persisted session state.

## Routes

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

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The root `package.json` also exposes:

```powershell
npm run backend:dev
```

## Configuration

The backend loads `.env` values from the repo root when present.

- `DEEPGRAM_API_KEY`: required for live Deepgram transcription and TTS routes
- `DEEPGRAM_MODEL`: defaults to `flux-general-en`
- `DEEPGRAM_LANGUAGE`: defaults to `en-US`
- `GROQ_API_KEY`: enables Groq-backed prepared questions and live faculty reasoning
- `FACULTY_AI_LLM_PROVIDER`: defaults to `heuristic`
- `FACULTY_AI_LLM_MODEL`: defaults to `qwen/qwen3-32b`
- `FACULTY_AI_SPEECH_PROVIDER`: defaults to `deepgram`
- `FACULTY_AI_ALLOWED_ORIGINS`: CORS allowlist
- `FACULTY_AI_APP_API_KEY`: required for non-local HTTP and WebSocket access

Localhost requests are allowed without an API key. Non-local HTTP requests must send `x-facultyai-key`. The WebSocket proxies accept the same value in either `x-facultyai-key` or the `key` query parameter.

## Persistence

State is stored in `faculty_ai.db` at the repository root:

- professor config
- session payloads and feedback history
- prepared-question cache

Without a `GROQ_API_KEY`, the backend falls back to deterministic heuristic preparation and feedback generation.
