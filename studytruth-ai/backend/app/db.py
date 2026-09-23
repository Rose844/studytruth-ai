"""
Lightweight SQLite persistence layer.

Tables:
  documents  - one row per uploaded/seeded document + metadata
  chunks     - one row per text chunk (used by the vector store on boot)
  quiz_log   - quiz attempts, for Study Analytics
  topic_progress - student-marked topic completion, for Exam Mode / Analytics
  chat_log   - Ask AI history, for the dashboard's "recent questions"
"""
import sqlite3
import json
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    subject TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    academic_year TEXT,
    version TEXT,
    upload_date TEXT,
    topic_tags TEXT,
    authority_rank INTEGER,
    char_count INTEGER,
    chunk_count INTEGER,
    full_text TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    chunk_index INTEGER,
    text TEXT NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents (doc_id)
);

CREATE TABLE IF NOT EXISTS quiz_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT,
    topic TEXT,
    question TEXT,
    correct INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS topic_progress (
    subject TEXT,
    topic TEXT,
    status TEXT DEFAULT 'not_started',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (subject, topic)
);

CREATE TABLE IF NOT EXISTS chat_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    tool_used TEXT,
    grounded INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subject_topics (
    subject TEXT NOT NULL,
    topic TEXT NOT NULL,
    source_doc_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (subject, topic)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def upsert_document(meta: Dict[str, Any], full_text: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO documents
               (doc_id, filename, subject, doc_type, academic_year, version,
                upload_date, topic_tags, authority_rank, char_count, chunk_count, full_text)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(doc_id) DO UPDATE SET
                 filename=excluded.filename, subject=excluded.subject,
                 doc_type=excluded.doc_type, academic_year=excluded.academic_year,
                 version=excluded.version, upload_date=excluded.upload_date,
                 topic_tags=excluded.topic_tags, authority_rank=excluded.authority_rank,
                 char_count=excluded.char_count, chunk_count=excluded.chunk_count,
                 full_text=excluded.full_text
            """,
            (
                meta["doc_id"], meta["filename"], meta["subject"], meta["doc_type"],
                meta.get("academic_year", "2025-26"), meta.get("version", "v1"),
                meta["upload_date"], json.dumps(meta.get("topic_tags", [])),
                meta["authority_rank"], meta.get("char_count", 0),
                meta.get("chunk_count", 0), full_text,
            ),
        )


def insert_chunks(doc_id: str, chunks: List[str]):
    with get_conn() as conn:
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        for i, text in enumerate(chunks):
            conn.execute(
                "INSERT INTO chunks (chunk_id, doc_id, chunk_index, text) VALUES (?,?,?,?)",
                (f"{doc_id}::chunk::{i}", doc_id, i, text),
            )


def get_all_documents() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY upload_date DESC").fetchall()
        return [_row_to_doc(r) for r in rows]


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        return _row_to_doc(row) if row else None


def get_all_chunks() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT chunks.*, documents.filename, documents.subject, documents.doc_type,
                      documents.version, documents.upload_date, documents.authority_rank,
                      documents.academic_year, documents.topic_tags
               FROM chunks JOIN documents ON chunks.doc_id = documents.doc_id"""
        ).fetchall()
        return [dict(r) for r in rows]


def _row_to_doc(row) -> Dict[str, Any]:
    d = dict(row)
    d["topic_tags"] = json.loads(d.get("topic_tags") or "[]")
    return d


def log_chat(query: str, tool_used: str, grounded: bool):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_log (query, tool_used, grounded) VALUES (?,?,?)",
            (query, tool_used, int(grounded)),
        )


def recent_chats(limit: int = 6) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def log_quiz(subject: str, topic: str, question: str, correct: bool):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO quiz_log (subject, topic, question, correct) VALUES (?,?,?,?)",
            (subject, topic, question, int(correct)),
        )


def quiz_stats() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT subject, topic,
                      SUM(correct) as correct_count,
                      COUNT(*) as total_count
               FROM quiz_log GROUP BY subject, topic"""
        ).fetchall()
        return [dict(r) for r in rows]


def set_topic_status(subject: str, topic: str, status: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO topic_progress (subject, topic, status, updated_at)
               VALUES (?,?,?,CURRENT_TIMESTAMP)
               ON CONFLICT(subject, topic) DO UPDATE SET
                 status=excluded.status, updated_at=CURRENT_TIMESTAMP""",
            (subject, topic, status),
        )


def get_topic_progress(subject: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        if subject:
            rows = conn.execute(
                "SELECT * FROM topic_progress WHERE subject = ?", (subject,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM topic_progress").fetchall()
        return [dict(r) for r in rows]


def clear_all():
    """Used by tests / re-seeding."""
    with get_conn() as conn:
        conn.executescript(
            "DELETE FROM documents; DELETE FROM chunks; DELETE FROM quiz_log;"
            "DELETE FROM topic_progress; DELETE FROM chat_log; DELETE FROM subject_topics;"
        )


def upsert_topics(subject: str, topics: List[str], source_doc_id: str = None):
    """Learn new topics for a subject automatically (called on every ingest)."""
    if not topics:
        return
    with get_conn() as conn:
        for topic in topics:
            conn.execute(
                """INSERT INTO subject_topics (subject, topic, source_doc_id)
                   VALUES (?,?,?)
                   ON CONFLICT(subject, topic) DO NOTHING""",
                (subject, topic, source_doc_id),
            )


def get_topics_for_subject(subject: str) -> List[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT topic FROM subject_topics WHERE subject = ? ORDER BY topic",
            (subject,),
        ).fetchall()
        return [r["topic"] for r in rows]


def get_all_subjects_with_topics() -> Dict[str, List[str]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT subject, topic FROM subject_topics").fetchall()
    result: Dict[str, List[str]] = {}
    for r in rows:
        result.setdefault(r["subject"], []).append(r["topic"])
    return result
