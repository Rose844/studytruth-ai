"""
Document ingestion pipeline:
  1. Text extraction (PDF via pypdf, or plain text)
  2. Chunking with overlap
  3. Lightweight topic-tag extraction (keyword/heading based)
  4. Metadata assembly (subject, type, date, version, authority rank)
  5. Persist to DB + trigger vector index rebuild
"""
from __future__ import annotations
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from pypdf import PdfReader

from app.config import settings
from app.models.schemas import AUTHORITY_RANK
from app.db import upsert_document, insert_chunks, upsert_topics, get_topics_for_subject
from app.utils.logger import get_logger

log = get_logger("document_processor")

# A small seed vocabulary for the 3 bundled demo subjects, kept only as a
# fallback / accuracy boost. It is NOT required for the app to work: any
# new subject the student adds gets its own topic list learned automatically
# at ingestion time by `extract_dynamic_topics()` below (from "UNIT n: ..."
# blocks in syllabi and "Lecture n: ..." headings in notes), and persisted
# in the `subject_topics` table via `db.upsert_topics()`. That's what makes
# "type anything into the Subject field and it just works" possible without
# touching this file.
TOPIC_VOCAB: Dict[str, List[str]] = {
    "computer networks": [
        "vlan", "osi model", "tcp/ip", "checksum", "subnetting", "ip addressing",
        "routing", "switching", "congestion control", "error detection",
        "flow control", "dns", "http", "tcp", "udp", "firewall", "nat",
        "ethernet", "wireless lan", "network security", "arp", "csma/cd",
    ],
    "deep neural networks": [
        "perceptron", "backpropagation", "activation function", "cnn",
        "rnn", "lstm", "gradient descent", "overfitting", "dropout",
        "batch normalization", "transfer learning", "autoencoder",
        "attention mechanism", "transformer", "loss function", "optimizer",
    ],
    "data structures and algorithms": [
        "array", "linked list", "stack", "queue", "tree", "binary search tree",
        "graph", "sorting", "searching", "dynamic programming", "recursion",
        "hashing", "heap", "greedy algorithm", "time complexity", "avl tree",
    ],
}

_STOPWORD_PHRASES = {
    "and", "or", "the", "a", "an", "of", "in", "on", "to", "with", "for",
    "its", "their", "such", "as", "etc", "e.g", "i.e", "note", "notes",
    "introduction", "overview", "basics", "applications", "example",
    "examples", "unit", "module",
}


def get_topic_vocab_for_subject(subject: str) -> List[str]:
    """
    The single source of truth every other module should call. Combines
    the small hardcoded seed list (if this is one of the bundled demo
    subjects) with whatever topics have been auto-learned from documents
    uploaded for this subject so far - so a brand-new subject with zero
    seed vocabulary still works the moment a syllabus is uploaded for it.
    """
    seed = set(TOPIC_VOCAB.get(subject.lower(), []))
    learned = set(get_topics_for_subject(subject))
    return sorted(seed | learned)


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        return file_path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, size: int = None, overlap: int = None) -> List[str]:
    size = size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        # try to end on a sentence/paragraph boundary
        boundary = text.rfind("\n", start, end)
        if boundary == -1 or boundary <= start + size * 0.5:
            boundary = end
        chunk = text[start:boundary].strip()
        if chunk:
            chunks.append(chunk)
        if boundary >= len(text):
            break
        start = max(boundary - overlap, start + 1)
    return chunks


def extract_topic_tags(text: str, subject: str) -> List[str]:
    vocab = get_topic_vocab_for_subject(subject)
    text_lower = text.lower()
    return sorted({topic for topic in vocab if topic in text_lower})


def _clean_phrase(phrase: str) -> str:
    phrase = re.sub(r"\s+", " ", phrase)  # collapse newlines/tabs/multi-space first
    phrase = phrase.strip(" \t\n.;:-–—•*")
    return phrase.lower()


def _is_valid_topic(phrase: str) -> bool:
    if not (3 <= len(phrase) <= 45):
        return False
    if phrase in _STOPWORD_PHRASES:
        return False
    if phrase.isdigit():
        return False
    if not re.search(r"[a-z]", phrase):
        return False
    # reject phrases that are themselves full sentences (too many words)
    if len(phrase.split()) > 6:
        return False
    return True


def extract_dynamic_topics(text: str, doc_type: str) -> List[str]:
    """
    Automatically learns topics from a document's own structure, with no
    per-subject configuration needed - this is what makes a brand-new
    subject work the moment its syllabus is uploaded:

      - Syllabus: finds "UNIT n: ..." / "Module n: ..." headings and splits
        the comma/semicolon-separated topic list that follows each one.
      - Lecture notes: finds "Lecture n: <title>" headings and uses each
        title directly as a topic (these are high-confidence, human-written
        topic names).
      - Fallback for any document type: splits comma-separated runs after
        colons anywhere in the text, which catches most "syllabus-style"
        writing even outside a dedicated Unit block.
    """
    topics: set[str] = set()

    # Unit / Module blocks (syllabus-style documents)
    unit_blocks = re.split(r"\n\s*(?:unit|module)\s*[-:]?\s*[0-9ivx]+", text, flags=re.IGNORECASE)
    for block in unit_blocks[1:]:  # skip preamble before the first heading
        block = block.split("\n\n")[0]  # stop at the next blank-line paragraph break
        # drop the heading title itself (text before the first colon on the heading line)
        first_colon = block.find(":")
        content = block[first_colon + 1:] if first_colon != -1 else block
        # if the heading title sits on its own line, drop that line too so it
        # doesn't get merged into the first real topic phrase
        lines = content.split("\n")
        body = "\n".join(lines[1:]) if len(lines) > 1 else content
        for raw in re.split(r"[,;]", body):
            cleaned = _clean_phrase(raw)
            if _is_valid_topic(cleaned):
                topics.add(cleaned)

    # Lecture-style headings (notes-style documents)
    for match in re.finditer(r"(?:lecture|lesson|topic)\s*[0-9]+\s*[:.\-]\s*([^\n]+)", text, flags=re.IGNORECASE):
        cleaned = _clean_phrase(match.group(1))
        if _is_valid_topic(cleaned):
            topics.add(cleaned)

    return sorted(topics)


def infer_authority_rank(doc_type: str) -> int:
    return AUTHORITY_RANK.get(doc_type, 6)


def ingest_document(
    file_path: Path,
    filename: str,
    subject: str,
    doc_type: str,
    academic_year: str = "2025-26",
    version: str = "v1",
    upload_date: str = None,
    doc_id: str = None,
) -> Dict[str, Any]:
    """Full ingestion pipeline for one document. Returns metadata dict."""
    upload_date = upload_date or datetime.utcnow().strftime("%Y-%m-%d")
    doc_id = doc_id or str(uuid.uuid4())[:8]

    text = extract_text(file_path)
    chunks = chunk_text(text)

    # Learn new topics for this subject from this document's own structure,
    # then tag the document against the combined (seed + learned) vocabulary.
    learned_topics = extract_dynamic_topics(text, doc_type)
    if learned_topics:
        upsert_topics(subject, learned_topics, source_doc_id=doc_id)
    topic_tags = extract_topic_tags(text, subject)

    meta = {
        "doc_id": doc_id,
        "filename": filename,
        "subject": subject,
        "doc_type": doc_type,
        "academic_year": academic_year,
        "version": version,
        "upload_date": upload_date,
        "topic_tags": topic_tags,
        "authority_rank": infer_authority_rank(doc_type),
        "char_count": len(text),
        "chunk_count": len(chunks),
    }

    upsert_document(meta, full_text=text)
    insert_chunks(doc_id, chunks)
    log.info(f"Ingested '{filename}' ({doc_type}, {subject}) -> {len(chunks)} chunks, "
              f"{len(learned_topics)} new topics learned, tags={topic_tags}")
    return meta
