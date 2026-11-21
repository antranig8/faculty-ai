# FacultyAI Frontend

Next.js app for professor setup and the live presentation cockpit. Setup and configuration are in the [root README](../README.md).

```powershell
npm install
npm run dev
```

Then open <http://localhost:3000>. Run `npm run lint` to type-check.

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
