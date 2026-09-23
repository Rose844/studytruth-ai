"""
Knowledge Conflict Detection engine - the signature feature of StudyTruth AI.

Given a topic (e.g. "VLAN") this module:
  1. Finds every document that is relevant to the topic within a subject.
  2. Splits them into "mentions it" vs "does not mention it".
  3. If documents disagree, or if the same topic is placed under a different
     unit/module across versions, it raises a structured conflict.
  4. Resolves the conflict using source_authority (rank + recency) and
     produces a plain-language explanation - never a silent choice.

`compare_documents()` implements the "Compare this year's syllabus with the
previous syllabus" / Conflict Checker UI feature: added / removed / modified
/ unchanged topics between any two documents.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional

from app.db import get_all_documents, get_document
from app.core.vector_store import get_vector_store
from app.core.source_authority import compare_authority, authority_confidence
from app.core.document_processor import get_topic_vocab_for_subject


def _unit_near_topic(full_text: str, topic: str) -> Optional[str]:
    """Best-effort: find 'Unit N' / 'Module N' mentioned near the topic keyword."""
    text = full_text.lower()
    idx = text.find(topic.lower())
    if idx == -1:
        return None
    window = text[max(0, idx - 400): idx + 200]
    match = re.search(r"(unit|module)\s*[-:]?\s*(\d+|[ivx]+)", window)
    return match.group(0).title() if match else None


def _doc_snippet_for_topic(full_text: str, topic: str, radius: int = 140) -> str:
    text_lower = full_text.lower()
    idx = text_lower.find(topic.lower())
    if idx == -1:
        return full_text[:radius].strip() + "..."
    start = max(0, idx - radius // 2)
    end = min(len(full_text), idx + len(topic) + radius)
    snippet = full_text[start:end].strip()
    return ("..." if start > 0 else "") + snippet + ("..." if end < len(full_text) else "")


def detect_conflicts_for_topic(topic: str, subject: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Look across all documents (optionally scoped to a subject) for
    disagreement about whether/where a topic is covered.
    Returns a list of conflict dicts ready to become ConflictItem models.
    """
    docs = get_all_documents()
    if subject:
        docs = [d for d in docs if d["subject"].lower() == subject.lower()]

    mentions, silent = [], []
    for d in docs:
        if d.get("full_text_missing"):
            continue
        full_text = _get_full_text(d["doc_id"])
        if not full_text:
            continue
        if topic.lower() in full_text.lower():
            mentions.append((d, full_text))
        else:
            # only count as "silent" if the doc type is one where we'd expect
            # topic coverage to be explicit (syllabus/notes), to avoid noise
            if d["doc_type"] in ("syllabus", "lecture_notes", "faculty_material"):
                silent.append((d, full_text))

    conflicts = []

    # Case 1: two syllabus-like docs disagree on unit placement
    unit_positions = {}
    for d, text in mentions:
        if d["doc_type"] == "syllabus":
            unit_positions[d["doc_id"]] = (_unit_near_topic(text, topic), d, text)

    unit_values = {v[0] for v in unit_positions.values() if v[0]}
    if len(unit_values) > 1:
        docs_list = list(unit_positions.values())
        for i in range(len(docs_list)):
            for j in range(i + 1, len(docs_list)):
                unit_a, doc_a, text_a = docs_list[i]
                unit_b, doc_b, text_b = docs_list[j]
                if unit_a and unit_b and unit_a != unit_b:
                    conflicts.append(_build_conflict(
                        topic, doc_a, doc_b,
                        f"'{topic}' appears under {unit_a} in {doc_a['filename']}.",
                        f"'{topic}' appears under {unit_b} in {doc_b['filename']}.",
                        text_a, text_b,
                    ))

    # Case 2: a syllabus mentions it, an older/other syllabus of the same
    # subject doesn't -> version conflict (this is the VLAN example)
    if mentions and silent:
        for d_silent, text_silent in silent:
            if d_silent["doc_type"] != "syllabus":
                continue
            for d_mention, text_mention in mentions:
                if d_mention["doc_type"] != "syllabus" or d_mention["doc_id"] == d_silent["doc_id"]:
                    continue
                conflicts.append(_build_conflict(
                    topic, d_mention, d_silent,
                    f"'{topic}' IS listed in {d_mention['filename']} ({d_mention['upload_date']}, {d_mention.get('version')}).",
                    f"'{topic}' is NOT mentioned in {d_silent['filename']} ({d_silent['upload_date']}, {d_silent.get('version')}).",
                    text_mention, text_silent,
                ))

    return conflicts


def _build_conflict(topic, doc_a, doc_b, statement_a, statement_b, text_a, text_b) -> Dict[str, Any]:
    winner, reason = compare_authority(doc_a, doc_b)
    confidence = authority_confidence(doc_a, doc_b)
    return {
        "topic": topic,
        "doc_a": _to_citation(doc_a, _doc_snippet_for_topic(text_a, topic)),
        "doc_b": _to_citation(doc_b, _doc_snippet_for_topic(text_b, topic)),
        "statement_a": statement_a,
        "statement_b": statement_b,
        "resolution": reason,
        "chosen_doc_id": winner["doc_id"] if confidence != "low" else None,
        "confidence": confidence,
    }


def _to_citation(doc: Dict[str, Any], snippet: str) -> Dict[str, Any]:
    return {
        "doc_id": doc["doc_id"], "filename": doc["filename"], "doc_type": doc["doc_type"],
        "subject": doc["subject"], "version": doc.get("version", ""),
        "upload_date": doc["upload_date"], "authority_rank": doc["authority_rank"],
        "snippet": snippet, "score": 1.0,
    }


def _get_full_text(doc_id: str) -> str:
    doc = get_document(doc_id)
    return doc.get("full_text", "") if doc else ""


# ---------------------------------------------------------------------------
# Conflict Checker: compare two whole documents (Added/Removed/Modified topics)
# ---------------------------------------------------------------------------
def compare_documents(doc_id_a: str, doc_id_b: str) -> Dict[str, Any]:
    doc_a, doc_b = get_document(doc_id_a), get_document(doc_id_b)
    if not doc_a or not doc_b:
        raise ValueError("One or both documents were not found")

    text_a, text_b = doc_a.get("full_text", ""), doc_b.get("full_text", "")
    vocab = get_topic_vocab_for_subject(doc_a["subject"])

    topics_a = {t for t in vocab if t in text_a.lower()}
    topics_b = {t for t in vocab if t in text_b.lower()}

    # Order by which doc is newer so "added/removed" reads naturally
    date_a, date_b = doc_a["upload_date"], doc_b["upload_date"]
    if date_a >= date_b:
        newer, older, newer_topics, older_topics = doc_a, doc_b, topics_a, topics_b
    else:
        newer, older, newer_topics, older_topics = doc_b, doc_a, topics_b, topics_a

    added = sorted(newer_topics - older_topics)
    removed = sorted(older_topics - newer_topics)
    common = newer_topics & older_topics

    modified = []
    unchanged = []
    for topic in sorted(common):
        unit_new = _unit_near_topic(newer.get("full_text", ""), topic)
        unit_old = _unit_near_topic(older.get("full_text", ""), topic)
        if unit_new and unit_old and unit_new != unit_old:
            modified.append(f"{topic} (moved from {unit_old} to {unit_new})")
        else:
            unchanged.append(topic)

    explanation_parts = [
        f"Comparing '{newer['filename']}' ({newer['upload_date']}) against "
        f"'{older['filename']}' ({older['upload_date']})."
    ]
    if added:
        explanation_parts.append(f"{len(added)} topic(s) were added: {', '.join(added)}.")
    if removed:
        explanation_parts.append(f"{len(removed)} topic(s) were removed: {', '.join(removed)}.")
    if modified:
        explanation_parts.append(f"{len(modified)} topic(s) moved position: {', '.join(modified)}.")
    if not added and not removed and not modified:
        explanation_parts.append("No major topic-level differences were detected between these documents.")

    return {
        "added_topics": added,
        "removed_topics": removed,
        "modified_topics": modified,
        "unchanged_topics": sorted(unchanged),
        "explanation": " ".join(explanation_parts),
        "doc_a": {k: v for k, v in doc_a.items() if k != "full_text"},
        "doc_b": {k: v for k, v in doc_b.items() if k != "full_text"},
    }
