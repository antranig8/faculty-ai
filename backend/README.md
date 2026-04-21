# FacultyAI Backend

FastAPI service for session management, presentation upload, live speech proxying, transcript analysis, and final evaluation.

## Endpoints

- `GET /health`
- `POST /session/start`
- `POST /analyze-chunk`
- `GET /session/{session_id}/feedback`
- `POST /session/{session_id}/finalize`
- `GET /session/results`
- `GET /professor/config`
- `POST /professor/config`
- `POST /presentation/upload`
- `POST /presentation/prepare`
- `POST /speech/{provider_name}/session`
- `WS /speech/deepgram/proxy`

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend reads configuration from the repo-root `.env` file. Localhost HTTP requests are allowed without an app API key. Non-local HTTP requests require `FACULTY_AI_APP_API_KEY` sent as `x-facultyai-key`; the Deepgram WebSocket proxy accepts the same key as either the `key` query parameter or `x-facultyai-key` header.

Set `DEEPGRAM_API_KEY` and `FACULTY_AI_SPEECH_PROVIDER=deepgram` to enable live microphone transcription through the backend proxy. The recommended demo model is `DEEPGRAM_MODEL=nova-3`.

Set `GROQ_API_KEY`, `FACULTY_AI_LLM_PROVIDER=groq`, and `FACULTY_AI_LLM_MODEL=qwen/qwen3-32b` to enable Groq-backed faculty reasoning and prepared-question generation. Without a Groq key, the backend falls back to deterministic heuristic question generation and evaluation.

