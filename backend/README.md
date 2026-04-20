# FacultyAI Backend

FastAPI service for session management and transcript chunk analysis.

## Endpoints

- `GET /health`
- `POST /session/start`
- `POST /analyze-chunk`
- `GET /session/{session_id}/feedback`

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The current analysis engine is deterministic and does not require network access or an API key.

