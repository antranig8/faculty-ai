from fastapi import APIRouter, File, HTTPException, UploadFile

import app.state as state
from app.models.request_models import PresentationPrepareRequest
from app.models.response_models import PresentationPrepareResponse
from app.services.llm_errors import classify_llm_error, log_llm_exception
from app.services.presentation_preparer import parse_slide_outline, prepare_questions, prepare_questions_with_llm
from app.services.pptx_parser import parse_pptx_slides

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _build_preparation_response(project_context, slides) -> PresentationPrepareResponse:
    cache_key = state.build_preparation_cache_key(project_context, slides)
    cached = state.prepared_question_cache.get(cache_key)
    if cached:
        return cached.model_copy(update={"cacheHit": True})

    llm_failure_reason: str | None = None
    try:
        prepared_questions = prepare_questions_with_llm(project_context, slides)
    except Exception as exc:
        log_llm_exception("prepare_questions_with_llm", exc)
        llm_failure_reason = classify_llm_error(exc)
        prepared_questions = None

    question_source = "llm"
    if prepared_questions is None:
        prepared_questions = prepare_questions(project_context, slides)
        question_source = "heuristic"

    response = PresentationPrepareResponse(
        slides=slides,
        preparedQuestions=prepared_questions,
        questionSource=question_source,
        cacheHit=False,
    )
    if question_source == "heuristic" and llm_failure_reason:
        response = response.model_copy(update={"cacheHit": False})
    state.save_prepared_question_cache(cache_key, response)
    return response

router = APIRouter(prefix="/presentation", tags=["presentation"])


@router.post("/prepare", response_model=PresentationPrepareResponse)
def prepare_presentation(payload: PresentationPrepareRequest) -> PresentationPrepareResponse:
    slides = parse_slide_outline(payload.slideOutline)
    return _build_preparation_response(payload.projectContext, slides)


@router.post("/upload", response_model=PresentationPrepareResponse)
async def upload_presentation(file: UploadFile = File(...)) -> PresentationPrepareResponse:
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Upload a .pptx presentation.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded presentation is empty.")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Presentation exceeds the 15 MB upload limit.")

    try:
        slides = parse_pptx_slides(file_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    project_context = state.professor_config_to_project_context()
    return _build_preparation_response(project_context, slides)
