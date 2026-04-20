from fastapi import APIRouter

import app.state as state
from app.models.request_models import ProfessorConfigRequest
from app.models.response_models import ProfessorConfig

router = APIRouter(prefix="/professor", tags=["professor"])


@router.get("/config", response_model=ProfessorConfig)
def get_professor_config() -> ProfessorConfig:
    return state.professor_config


@router.post("/config", response_model=ProfessorConfig)
def save_professor_config(payload: ProfessorConfigRequest) -> ProfessorConfig:
    state.professor_config = payload.config
    return state.professor_config
