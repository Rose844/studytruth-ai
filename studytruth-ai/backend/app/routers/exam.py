from fastapi import APIRouter
from app.models.schemas import StudyPlanRequest
from app.core import tools

router = APIRouter(prefix="/api/exam", tags=["exam"])


@router.post("/study-plan")
def study_plan(payload: StudyPlanRequest):
    return tools.create_study_plan(payload.subject, completed_topics=payload.completed_topics)


@router.get("/pyqs")
def pyqs(topic: str, subject: str = None):
    return {"topic": topic, "results": tools.find_pyqs(topic, subject=subject)}
