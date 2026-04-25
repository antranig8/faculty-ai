# FacultyAI Frontend

Next.js 16 app for professor setup, presentation rehearsal, access-code gating, and live faculty-question playback.

## Routes

- `/`: landing page with links to setup and presentation mode
- `/access`: optional access-code form when `FACULTY_AI_ACCESS_CODE` is set
- `/professor`: professor rubric and assignment setup
- `/present`: presentation cockpit
- `/results`: currently redirects to `/present`

## Development

```powershell
npm install
npm run dev
```

Open `http://localhost:3000/`.

The root `package.json` also exposes:

```powershell
npm run frontend:dev
```

## Configuration

- `NEXT_PUBLIC_API_BASE_URL`: backend base URL, defaults to `http://localhost:8000`
- `NEXT_PUBLIC_FACULTY_AI_APP_API_KEY`: optional key forwarded to protected backend HTTP and WebSocket routes
- `FACULTY_AI_ACCESS_CODE`: enables the access page and signed cookie session check

## Current Behavior

- Uploads `.pptx` files and prepares slide-aware faculty questions
- Starts live mic mode against the backend Deepgram proxy
- Infers the active slide automatically, with manual override available
- Speaks triggered faculty questions with Deepgram TTS when enabled
- Lets users resolve or reopen faculty questions in the feedback drawer
- Shows queued questions, answer-quality state, and targeted-student metadata when available
