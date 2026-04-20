from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.request_models import PresentationPrepareRequest
from app.models.response_models import PresentationPrepareResponse
from app.services.presentation_preparer import parse_slide_outline, prepare_questions
from app.services.pptx_parser import parse_pptx_slides
import app.state as state

router = APIRouter(prefix="/presentation", tags=["presentation"])


@router.post("/prepare", response_model=PresentationPrepareResponse)
def prepare_presentation(payload: PresentationPrepareRequest) -> PresentationPrepareResponse:
    slides = parse_slide_outline(payload.slideOutline)
    prepared_questions = prepare_questions(payload.projectContext, slides)
    return PresentationPrepareResponse(slides=slides, preparedQuestions=prepared_questions)


@router.post("/upload", response_model=PresentationPrepareResponse)
async def upload_presentation(file: UploadFile = File(...)) -> PresentationPrepareResponse:
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Upload a .pptx presentation.")

    try:
        slides = parse_pptx_slides(await file.read())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    project_context = state.professor_config_to_project_context()
    prepared_questions = prepare_questions(project_context, slides)
    return PresentationPrepareResponse(slides=slides, preparedQuestions=prepared_questions)
