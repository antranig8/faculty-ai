# FacultyAI

ENES 104 AI faculty member.

FacultyAI is a demo-safe presentation assistant. It accepts project context, sends transcript chunks to a backend, and surfaces faculty-style questions or critiques as visible alerts.

## Current Build

- Next.js frontend in `frontend/`
- FastAPI backend in `backend/`
- Fake transcript demo mode
- Rubric and slide outline preparation
- Professor-owned rubric configuration
- Student-only `.pptx` upload flow
- Slide-specific prepared faculty questions
- Manual current-slide tracking
- In-memory sessions and feedback history
- Cooldown and duplicate filtering
- Heuristic feedback engine that works without an LLM key

## Run Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

## Run Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/present`.

## Demo Flow

1. Start the backend.
2. Start the frontend.
3. Open presentation mode.
4. Open professor setup at `http://localhost:3000/professor` and save the rubric.
5. Open student presentation mode at `http://localhost:3000/present`.
6. Upload a `.pptx`.
7. Click `Start demo`.
8. Advance slides manually while sending transcript chunks.
9. When the `!` appears, click it to open the faculty feedback drawer.

## Direction

The current product direction is documented in:

- `docs/slide_aware_faculty_examiner_direction.md`

FacultyAI should behave like a selective faculty examiner, not a general helper. It should use rubric criteria, current slide context, and live transcript content to decide whether a faculty-style remark is warranted.

Speech provider direction is documented in:

- `docs/speech_provider_split.md`

## Next Good Steps

1. Add browser speech recognition and transcript chunking.
2. Replace the heuristic engine with an LLM service behind the same response contract.
3. Add a cached demo mode with pre-generated feedback for class presentations.
4. Persist sessions to a lightweight database.
