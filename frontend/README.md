# Faculty-AI Frontend

Next.js app for professor setup, live rehearsal, and saved results. Use `npm run dev` from the repository root to start both services. To run just the frontend for debugging, use these commands from this directory.

```powershell
npm ci
npm run dev -- --hostname 127.0.0.1
```

Then open <http://127.0.0.1:3000>. Run `npm run lint` and `npm run build` to match the frontend checks in GitHub Actions.

The frontend loads `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_FACULTY_AI_APP_API_KEY`, and `FACULTY_AI_ACCESS_CODE` from the repository-root `.env` when they are absent from the frontend environment. The root launcher points the frontend to the local backend and skips the optional access prompt.

## Pages

| Route | Purpose |
|---|---|
| `/` | Landing page |
| `/professor` | Rubric, assignment context, and questioning style |
| `/present` | Live slide tracker, animated faculty questions, and expandable transcript, feedback, and session details |
| `/results` | Saved faculty questions and their status from the latest rehearsal in this browser |
| `/access` | Access-code prompt, shown only when `FACULTY_AI_ACCESS_CODE` is set |

Use the **Professor**, **Present**, and **Results** links on each rehearsal page. In **Present**, drop a `.pptx` onto the upload area or choose it with the file picker. Moving forward in **Manual lock** marks the on-screen question addressed.

Use the sun or moon button in the header to switch between light and dark mode. The browser remembers your selection. The app follows your system theme until you choose one.

For a test upload, use the [sample rehearsal deck](../docs/sample-rehearsal.pptx).

## Layout

- `app/`: pages and the `/api/access` route that issues the signed access cookie
- `components/`: navigation, theme controls, cockpit UI, and rehearsal details
- `lib/api.ts`: backend client, including the speech WebSocket URLs
- `lib/theme.ts`: restores the browser theme before the app renders
- `lib/accessSession.ts`, `proxy.ts`: access-code gate
