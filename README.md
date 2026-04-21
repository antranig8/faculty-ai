# FacultyAI

ENES 104 AI faculty member.

FacultyAI is a live presentation critique assistant for ENES 104 style project demos. It listens to a presenter, matches speech against uploaded slides and rubric-aware concerns, and surfaces selective faculty-style questions plus a final rubric-based grade.

## Current Build

- Next.js frontend in `frontend/`
- FastAPI backend in `backend/`
- Root `.env` configuration
- `.pptx` upload and slide parsing
- Slide-specific prepared faculty questions
- Live mic transcription through Deepgram
- Transcript-driven slide inference
- Structured faculty-question reasoning
- SQLite persistence for sessions/results/cache
- Final rubric-based grading
- Demo transcript mode as fallback
- Cooldown, dedupe, and one-question-per-slide enforcement

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
3. Open `http://localhost:3000/present`.
4. Upload a `.pptx`.
5. Click `Start live mic` for the real path or `Start demo` for fake transcript mode.
6. Speak through the presentation.
7. When a faculty question triggers, the drawer opens automatically.
8. Click `Finalize grade` at the end.
9. Review saved results at `http://localhost:3000/results`.

## Direction

Current direction and carry-forward status are documented in:

- `docs/slide_aware_faculty_examiner_direction.md`
- `docs/project_update_2026-04-20.md`

FacultyAI should behave like a selective faculty examiner, not a general helper. It should use rubric criteria, current slide context, and live transcript content to decide whether a faculty-style remark is warranted.

Speech provider direction is documented in:

- `docs/speech_provider_split.md`

## Next Good Steps

1. Keep tuning the live Nova-3 path for transcript quality and stability.
2. Reduce Groq token usage further if TPM limits still disrupt live testing.
3. Add answer-resolution handling so addressed faculty questions can turn green and dismiss cleanly.
4. Continue improving transcript-based slide inference so manual slide controls become only a fallback.
