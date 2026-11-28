# Faculty-AI Frontend

Next.js app for professor setup and the live presentation cockpit. Use `npm run dev` from the repository root to start both services. To run just the frontend for debugging, use these commands from this directory.

```powershell
npm ci
npm run dev -- --hostname 127.0.0.1
```

Then open <http://127.0.0.1:3000>. Run `npm run lint` to type-check.

The frontend loads `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_FACULTY_AI_APP_API_KEY`, and `FACULTY_AI_ACCESS_CODE` from the repository-root `.env` when they are absent from the frontend environment. The root launcher points the frontend to the local backend and skips the optional access prompt.

## Pages

| Route | Purpose |
|---|---|
| `/` | Landing page |
| `/professor` | Rubric, assignment context, and questioning style |
| `/present` | Deck upload, live transcript, slide tracker, and feedback drawer |
| `/access` | Access-code prompt, shown only when `FACULTY_AI_ACCESS_CODE` is set |

## Layout

- `app/`: pages and the `/api/access` route that issues the signed access cookie
- `components/`: cockpit UI (upload, slide tracker, transcript, feedback drawer, alerts)
- `lib/api.ts`: backend client, including the speech WebSocket URLs
- `lib/accessSession.ts`, `proxy.ts`: access-code gate
