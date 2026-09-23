import re
from datetime import datetime, UTC
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from app.db import (
    get_all_documents, quiz_stats, get_topic_progress, set_topic_status,
    recent_chats,
)
from app.core import tools

router = APIRouter(prefix="/api", tags=["analytics"])

EXAM_DATE_RE = re.compile(r"exam date\s*:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def _get_upcoming_exams():
    """
    Best-effort extraction of exam dates from 'notice' / 'exam_instructions'
    documents (looks for an 'Exam Date: YYYY-MM-DD' line). Real deployments
    would model this as structured metadata rather than parsing free text;
    this is a lightweight MVP heuristic on top of the same document store.
    """
    docs = get_all_documents()
    today = datetime.now(UTC).date()
    upcoming = []
    for d in docs:
        if d["doc_type"] not in ("notice", "exam_instructions"):
            continue
        match = EXAM_DATE_RE.search(d.get("full_text", "") or "")
        if not match:
            continue
        try:
            exam_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        days_left = (exam_date - today).days
        upcoming.append({
            "subject": d["subject"], "exam_date": match.group(1),
            "days_left": days_left, "source_doc_id": d["doc_id"],
            "filename": d["filename"],
        })
    upcoming.sort(key=lambda e: e["exam_date"])
    return upcoming


def _get_study_progress(subjects):
    progress = []
    for subject in subjects:
        plan = tools.create_study_plan(subject)
        total = plan["total_topics"]
        remaining = plan["topics_remaining"]
        done = total - remaining
        pct = round((done / total) * 100) if total else 0
        progress.append({"subject": subject, "topics_done": done, "topics_total": total, "percent": pct})
    return progress


@router.get("/analytics")
def analytics(subject: Optional[str] = None):
    stats = quiz_stats()
    if subject:
        stats = [s for s in stats if s["subject"].lower() == subject.lower()]

    weak_topics = []
    for s in stats:
        total = s["total_count"] or 1
        accuracy = (s["correct_count"] or 0) / total
        if accuracy < 0.6:
            weak_topics.append({**s, "accuracy": round(accuracy, 2)})
    weak_topics.sort(key=lambda x: x["accuracy"])

    progress = get_topic_progress(subject)
    done = len([p for p in progress if p["status"] == "done"])

    return {
        "quiz_stats": stats,
        "weak_topics": weak_topics,
        "topic_progress": progress,
        "topics_done": done,
        "topics_total": len(progress),
    }


class TopicStatusUpdate(BaseModel):
    subject: str
    topic: str
    status: str  # not_started | in_progress | done


@router.post("/topic-status")
def update_topic_status(payload: TopicStatusUpdate):
    set_topic_status(payload.subject, payload.topic, payload.status)
    return {"status": "ok"}


@router.get("/dashboard")
def dashboard():
    docs = get_all_documents()
    subjects = sorted({d["subject"] for d in docs})
    subject_counts = {s: len([d for d in docs if d["subject"] == s]) for s in subjects}
    stats = quiz_stats()
    total_attempts = sum(s["total_count"] for s in stats)
    total_correct = sum(s["correct_count"] for s in stats)
    accuracy = round((total_correct / total_attempts) * 100, 1) if total_attempts else None

    return {
        "subjects": subjects,
        "subject_document_counts": subject_counts,
        "total_documents": len(docs),
        "recent_questions": recent_chats(6),
        "quiz_accuracy_percent": accuracy,
        "total_quiz_attempts": total_attempts,
        "upcoming_exams": _get_upcoming_exams(),
        "study_progress": _get_study_progress(subjects),
    }
