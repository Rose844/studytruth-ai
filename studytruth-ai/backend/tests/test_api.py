"""
Test suite for StudyTruth AI backend.

Run with (from the backend/ folder):
    pytest tests/ -v

These tests seed a temporary copy of the sample data so they don't depend
on manual setup, then exercise the real RAG + conflict detection + agent
pipeline end-to-end (no mocking) - the same code path the UI uses.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import init_db, clear_all
from app.core.document_processor import ingest_document
from app.core.vector_store import rebuild_vector_store

SAMPLE_DIR = ROOT / "sample_data"


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    init_db()
    clear_all()
    docs = [
        ("computer_networks/syllabus_2025_v2.txt", "Computer Networks", "syllabus", "2025-26", "v2", "2025-08-01", "cn-syl-v2"),
        ("computer_networks/syllabus_2023_v1.txt", "Computer Networks", "syllabus", "2023-24", "v1", "2023-07-01", "cn-syl-v1"),
        ("computer_networks/lecture_notes_unit3.txt", "Computer Networks", "lecture_notes", "2025-26", "v1", "2025-09-10", "cn-notes-u3"),
        ("computer_networks/pyqs_cn.txt", "Computer Networks", "pyq", "2025-26", "v1", "2025-01-15", "cn-pyq-1"),
        ("computer_networks/assignment_1.txt", "Computer Networks", "assignment", "2025-26", "v1", "2025-09-05", "cn-assign-1"),
        ("dsa/syllabus.txt", "Data Structures and Algorithms", "syllabus", "2025-26", "v1", "2025-08-01", "dsa-syl-v1"),
        ("dsa/pyqs.txt", "Data Structures and Algorithms", "pyq", "2025-26", "v1", "2025-01-15", "dsa-pyq-1"),
    ]
    for rel_path, subject, doc_type, year, version, date, doc_id in docs:
        ingest_document(
            file_path=SAMPLE_DIR / rel_path, filename=Path(rel_path).name,
            subject=subject, doc_type=doc_type, academic_year=year,
            version=version, upload_date=date, doc_id=doc_id,
        )
    rebuild_vector_store()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_documents_listed(client):
    res = client.get("/api/documents")
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) == 7
    assert any(d["filename"] == "syllabus_2025_v2.txt" for d in docs)


def test_vlan_conflict_detected(client):
    """The flagship demo scenario: VLAN conflict between syllabus versions."""
    res = client.post("/api/ask", json={"query": "Is VLAN included in my CN syllabus?"})
    assert res.status_code == 200
    data = res.json()
    assert data["grounded"] is True
    assert len(data["conflicts"]) >= 1
    conflict = data["conflicts"][0]
    assert conflict["chosen_doc_id"] == "cn-syl-v2"  # newer syllabus wins
    assert "vlan" in conflict["topic"].lower()


def test_conflict_detector_directly(client):
    res = client.get("/api/conflicts/detect", params={"topic": "vlan", "subject": "Computer Networks"})
    assert res.status_code == 200
    data = res.json()
    assert data["has_conflicts"] is True


def test_compare_documents_added_topics(client):
    res = client.post("/api/conflicts/compare", json={"doc_id_a": "cn-syl-v2", "doc_id_b": "cn-syl-v1"})
    assert res.status_code == 200
    data = res.json()
    assert "vlan" in data["added_topics"]


def test_grounded_answer_has_citations(client):
    res = client.post("/api/ask", json={"query": "What is checksum?", "subject": "Computer Networks"})
    data = res.json()
    assert data["grounded"] is True
    assert len(data["citations"]) > 0
    assert data["confidence"] in ("high", "medium", "low")


def test_ungrounded_question_does_not_hallucinate(client):
    res = client.post("/api/ask", json={"query": "What is the capital of Mars colony Zeta-9?"})
    data = res.json()
    assert data["grounded"] is False
    assert "couldn't find this information" in data["answer"].lower()
    assert data["ai_generated_note"] is not None


def test_study_plan_prioritizes_pyq_frequency(client):
    res = client.post("/api/exam/study-plan", json={"subject": "Computer Networks", "completed_topics": []})
    data = res.json()
    assert data["total_topics"] > 0
    # checksum appears across multiple years of PYQs -> should be high priority
    checksum = next((t for t in data["plan"] if t["topic"] == "checksum"), None)
    assert checksum is not None
    assert checksum["priority"] in ("high", "medium")


def test_quiz_generation_is_grounded(client):
    res = client.post("/api/quiz/generate", json={"topic": "vlan", "subject": "Computer Networks", "num_questions": 3})
    data = res.json()
    assert data["grounded"] is True
    assert len(data["questions"]) > 0
    for q in data["questions"]:
        assert len(q["options"]) >= 2
        assert 0 <= q["correct_index"] < len(q["options"])


def test_agent_routes_quiz_intent(client):
    res = client.post("/api/ask", json={"query": "Give me 5 MCQs on VLAN", "subject": "Computer Networks"})
    data = res.json()
    assert data["tool_used"] == "generate_quiz"
    assert "quiz" in data


def test_agent_routes_study_plan_intent(client):
    res = client.post("/api/ask", json={"query": "What should I study for my CN exam tomorrow?"})
    data = res.json()
    assert data["tool_used"] == "create_study_plan"


def test_agent_routes_compare_intent(client):
    res = client.post("/api/ask", json={"query": "I have two syllabi. What changed?", "subject": "Computer Networks"})
    data = res.json()
    assert data["tool_used"] == "compare_documents"
    assert "comparison" in data


def test_dashboard_endpoint(client):
    res = client.get("/api/dashboard")
    data = res.json()
    assert data["total_documents"] == 7
    assert "Computer Networks" in data["subjects"]


def test_source_authority_ranking():
    from app.models.schemas import AUTHORITY_RANK
    assert AUTHORITY_RANK["syllabus"] < AUTHORITY_RANK["pyq"]
    assert AUTHORITY_RANK["faculty_material"] < AUTHORITY_RANK["assignment"]


def test_new_subject_works_with_zero_configuration(client):
    """
    The whole point of dynamic topic learning: a subject that was never
    hardcoded anywhere in the code should still get topic-tagged, and
    Study Plan / Ask AI / Quiz should all work for it immediately after
    a syllabus + PYQ upload - no code changes required.
    """
    syllabus_text = (
        "TESTABLE SUBJECT - SYLLABUS\n\n"
        "UNIT 1: Foundations\n"
        "widget theory, gadget analysis, sprocket design.\n\n"
        "UNIT 2: Advanced Widgets\n"
        "quantum widgets, distributed gadgets, sprocket optimization.\n"
    )
    pyq_text = (
        "PREVIOUS YEAR QUESTIONS\n\n"
        "2024:\nQ1. Explain widget theory in detail.\nQ2. Explain widget theory with an example.\n"
    )
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        syl_path = Path(tmp) / "syllabus.txt"
        syl_path.write_text(syllabus_text)
        pyq_path = Path(tmp) / "pyqs.txt"
        pyq_path.write_text(pyq_text)

        ingest_document(file_path=syl_path, filename="syllabus.txt", subject="Testable Subject",
                         doc_type="syllabus", upload_date="2025-09-01", doc_id="test-syl-1")
        ingest_document(file_path=pyq_path, filename="pyqs.txt", subject="Testable Subject",
                         doc_type="pyq", upload_date="2025-01-01", doc_id="test-pyq-1")
        rebuild_vector_store()

    # Study plan should surface "widget theory" as high priority (2 PYQ mentions)
    plan_res = client.post("/api/exam/study-plan", json={"subject": "Testable Subject"})
    plan = plan_res.json()
    assert plan["total_topics"] > 0
    widget_topic = next((t for t in plan["plan"] if "widget theory" in t["topic"]), None)
    assert widget_topic is not None
    assert widget_topic["pyq_frequency"] >= 1

    # Ask AI should answer grounded, from this brand-new subject's material
    ask_res = client.post("/api/ask", json={"query": "What is widget theory?", "subject": "Testable Subject"})
    ask_data = ask_res.json()
    assert ask_data["grounded"] is True
