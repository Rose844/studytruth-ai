from typing import List, Optional, Literal
from pydantic import BaseModel, Field


DocType = Literal[
    "syllabus", "lecture_notes", "faculty_material", "assignment",
    "pyq", "lab_manual", "exam_instructions", "notice", "other",
]

# Source authority ranking (1 = highest priority). Mirrors README priority table.
AUTHORITY_RANK = {
    "notice": 1,             # latest official syllabus / official notice
    "syllabus": 1,
    "faculty_material": 2,
    "lecture_notes": 3,
    "assignment": 4,
    "lab_manual": 4,
    "exam_instructions": 2,
    "pyq": 5,
    "other": 6,
}


class DocumentMetadata(BaseModel):
    doc_id: str
    filename: str
    subject: str
    doc_type: DocType
    academic_year: str = "2025-26"
    version: str = "v1"
    upload_date: str
    topic_tags: List[str] = []
    authority_rank: int
    char_count: int = 0
    chunk_count: int = 0


class DocumentOut(DocumentMetadata):
    preview: Optional[str] = None


class AskRequest(BaseModel):
    query: str
    subject: Optional[str] = None
    completed_topics: Optional[List[str]] = None


class Citation(BaseModel):
    doc_id: str
    filename: str
    doc_type: str
    subject: str
    version: str
    upload_date: str
    authority_rank: int
    snippet: str
    score: float


class ConflictItem(BaseModel):
    topic: str
    doc_a: Citation
    doc_b: Citation
    statement_a: str
    statement_b: str
    resolution: str
    chosen_doc_id: Optional[str]
    confidence: Literal["high", "medium", "low"]


class AskResponse(BaseModel):
    answer: str
    grounded: bool
    confidence: Literal["high", "medium", "low", "none"]
    citations: List[Citation]
    conflicts: List[ConflictItem] = []
    ai_generated_note: Optional[str] = None
    tool_used: str
    reasoning_trace: List[str] = []


class CompareRequest(BaseModel):
    doc_id_a: str
    doc_id_b: str


class CompareResponse(BaseModel):
    added_topics: List[str]
    removed_topics: List[str]
    modified_topics: List[str]
    unchanged_topics: List[str]
    explanation: str
    doc_a: DocumentMetadata
    doc_b: DocumentMetadata


class QuizRequest(BaseModel):
    topic: str
    subject: Optional[str] = None
    num_questions: int = 5


class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_index: int
    explanation: str
    source_doc_id: Optional[str] = None
    topic: str


class QuizResponse(BaseModel):
    topic: str
    questions: List[QuizQuestion]
    grounded: bool


class StudyPlanRequest(BaseModel):
    subject: str
    exam_date: Optional[str] = None
    completed_topics: List[str] = []


class StudyPlanTopic(BaseModel):
    topic: str
    priority: Literal["high", "medium", "low"]
    reason: str
    pyq_frequency: int
    status: Literal["not_started", "in_progress", "done"]
    source_doc_id: Optional[str] = None


class StudyPlanResponse(BaseModel):
    subject: str
    plan: List[StudyPlanTopic]
    summary: str
    total_topics: int
    topics_remaining: int
