from fastapi import APIRouter
from app.models.schemas import AskRequest
from app.core.agent import handle_query

router = APIRouter(prefix="/api", tags=["ask"])


@router.post("/ask")
def ask(payload: AskRequest):
    """
    Unified 'Ask My Study Material' + Study Agent endpoint.
    The agent decides internally which tool(s) to use (search, quiz,
    study plan, comparison, conflict detection, PYQ lookup, summary) and
    returns a grounded, cited response plus a reasoning trace.
    """
    return handle_query(payload.query, subject=payload.subject, completed_topics=payload.completed_topics)
