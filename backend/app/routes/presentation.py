from fastapi import APIRouter, File, HTTPException, UploadFile

import app.state as state
from app.config import get_settings
from app.models.request_models import PresentationPrepareRequest, ProjectContext
from app.models.response_models import PresentationPrepareResponse, Slide
from app.services.llm_errors import log_llm_exception
from app.services.presentation_preparer import parse_slide_outline, prepare_questions, prepare_questions_with_llm
from app.services.pptx_parser import InvalidPresentationError, parse_pptx_slides

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _build_preparation_response(project_context: ProjectContext, slides: list[Slide]) -> PresentationPrepareResponse:
    settings = get_settings()
    groq_model = settings.faculty_ai_llm_model if settings.uses_groq else None
    cache_key = state.build_preparation_cache_key(project_context, slides, groq_model=groq_model)
    cached = state.get_prepared_question_cache(cache_key)
    if cached:
        return cached.model_copy(update={"cacheHit": True})

    try:
        prepared_questions = prepare_questions_with_llm(project_context, slides)
    except Exception as exc:
        log_llm_exception("prepare_questions_with_llm", exc)
        prepared_questions = None

    question_source = "llm"
    if prepared_questions is None:
        prepared_questions = prepare_questions(project_context, slides)
        question_source = "heuristic"
    else:
        covered_slide_numbers = {question.slideNumber for question in prepared_questions}
        gap_questions = [
            question
            for question in prepare_questions(project_context, slides)
            if question.slideNumber not in covered_slide_numbers
        ]
        prepared_questions = [*prepared_questions, *gap_questions]

    response = PresentationPrepareResponse(
        slides=slides,
        preparedQuestions=prepared_questions,
        questionSource=question_source,
        cacheHit=False,
    )
    # A transient provider failure must not pin this deck to heuristic questions.
    if groq_model is None or question_source == "llm":
        state.save_prepared_question_cache(cache_key, response)
    return response


router = APIRouter(prefix="/presentation", tags=["presentation"])


@router.post("/prepare", response_model=PresentationPrepareResponse)
def prepare_presentation(payload: PresentationPrepareRequest) -> PresentationPrepareResponse:
    slides = parse_slide_outline(payload.slideOutline)
    return _build_preparation_response(payload.projectContext, slides)


@router.post("/upload", response_model=PresentationPrepareResponse)
def upload_presentation(file: UploadFile = File(...)) -> PresentationPrepareResponse:
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Upload a .pptx presentation.")

    file_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded presentation is empty.")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Presentation exceeds the 15 MB upload limit.")

    try:
        slides = parse_pptx_slides(file_bytes)
    except InvalidPresentationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not slides:
        raise HTTPException(status_code=400, detail="The presentation contains no slides.")

    project_context = state.professor_config_to_project_context()
    return _build_preparation_response(project_context, slides)
