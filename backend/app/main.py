import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes import analyze, presentation, professor, session, speech
from app.security import is_local_host

app = FastAPI(title="Faculty AI Live Feedback")
logging.basicConfig(level=logging.INFO)
settings = get_settings()
PUBLIC_PATHS = {"/", "/health"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.faculty_ai_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_key_for_non_local_requests(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    if is_local_host(request.client.host if request.client else None):
        return await call_next(request)

    required_key = get_settings().faculty_ai_app_api_key
    if not required_key:
        return JSONResponse(
            status_code=403,
            content={"detail": "Non-local access is disabled until FACULTY_AI_APP_API_KEY is configured."},
        )

    if request.headers.get("x-facultyai-key") != required_key:
        return JSONResponse(status_code=401, content={"detail": "Missing or invalid API key."})

    return await call_next(request)


app.include_router(session.router)
app.include_router(analyze.router)
app.include_router(presentation.router)
app.include_router(professor.router)
app.include_router(speech.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Faculty AI Backend", "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
