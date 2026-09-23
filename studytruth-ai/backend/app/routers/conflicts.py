from typing import Optional
from fastapi import APIRouter, HTTPException
from app.models.schemas import CompareRequest
from app.core.conflict_detector import compare_documents, detect_conflicts_for_topic

router = APIRouter(prefix="/api/conflicts", tags=["conflicts"])


@router.post("/compare")
def compare(payload: CompareRequest):
    try:
        return compare_documents(payload.doc_id_a, payload.doc_id_b)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/detect")
def detect(topic: str, subject: Optional[str] = None):
    conflicts = detect_conflicts_for_topic(topic, subject=subject)
    return {"topic": topic, "conflicts": conflicts, "has_conflicts": bool(conflicts)}
