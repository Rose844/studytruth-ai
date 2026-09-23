from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from app.models.schemas import QuizRequest
from app.core import tools
from app.db import log_quiz, quiz_stats

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


@router.post("/generate")
def generate(payload: QuizRequest):
    return tools.generate_quiz(payload.topic, subject=payload.subject, num_questions=payload.num_questions)


class QuizAnswerLog(BaseModel):
    subject: Optional[str] = None
    topic: str
    question: str
    correct: bool


@router.post("/log")
def log_answer(payload: QuizAnswerLog):
    log_quiz(payload.subject or "general", payload.topic, payload.question, payload.correct)
    return {"status": "logged"}


@router.get("/stats")
def stats():
    return quiz_stats()
