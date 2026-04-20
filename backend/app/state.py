from app.models.request_models import ProjectContext
from app.models.response_models import ProfessorConfig

sessions = {}
professor_config = ProfessorConfig()


def professor_config_to_project_context() -> ProjectContext:
    return ProjectContext(
        title=professor_config.assignmentName,
        summary=professor_config.assignmentContext,
        stack=[],
        goals=[],
        rubric=professor_config.rubric,
        notes=professor_config.questionStyle,
    )
