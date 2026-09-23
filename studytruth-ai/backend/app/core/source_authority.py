"""
Source Reliability engine.

Decides, given two (or more) documents that discuss the same topic, which
one should be trusted - and produces a plain-language justification. This
is the core of the "Knowledge Conflict Detection" feature: the system must
never silently pick a source; it always explains itself.

Priority order (lower rank number = more authoritative), matches README:
  1. Latest official syllabus / official notice
  2. Faculty-provided material / exam instructions
  3. Latest lecture notes
  4. Assignments / lab manuals
  5. Previous year question papers
  6. Older / unclassified documents
"""
from __future__ import annotations
from typing import Dict, Any, Tuple
from datetime import datetime

AUTHORITY_LABEL = {
    1: "official syllabus / notice",
    2: "faculty-provided material",
    3: "lecture notes",
    4: "assignment / lab manual",
    5: "previous year question paper",
    6: "unclassified / older document",
}


def _parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return datetime(1970, 1, 1)


def compare_authority(doc_a: Dict[str, Any], doc_b: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """
    Returns (chosen_doc, explanation). Rules, in order:
      1. Lower authority_rank number wins outright (syllabus beats PYQ, etc.)
      2. If same authority rank, the more recent upload_date / version wins.
      3. If still tied, we report genuine uncertainty (caller should surface this).
    """
    rank_a, rank_b = doc_a["authority_rank"], doc_b["authority_rank"]

    if rank_a != rank_b:
        winner, loser = (doc_a, doc_b) if rank_a < rank_b else (doc_b, doc_a)
        reason = (
            f"'{winner['filename']}' is a {AUTHORITY_LABEL.get(winner['authority_rank'], 'document')}, "
            f"which ranks higher in authority than '{loser['filename']}' "
            f"({AUTHORITY_LABEL.get(loser['authority_rank'], 'document')}). "
            f"Official/syllabus-level sources override notes and past papers."
        )
        return winner, reason

    date_a, date_b = _parse_date(doc_a["upload_date"]), _parse_date(doc_b["upload_date"])
    if date_a != date_b:
        winner, loser = (doc_a, doc_b) if date_a > date_b else (doc_b, doc_a)
        reason = (
            f"Both documents are of the same type ({AUTHORITY_LABEL.get(winner['authority_rank'])}), "
            f"but '{winner['filename']}' ({winner['upload_date']}, {winner.get('version','')}) "
            f"is more recent than '{loser['filename']}' ({loser['upload_date']}, {loser.get('version','')}). "
            f"The latest version is treated as authoritative."
        )
        return winner, reason

    reason = (
        f"'{doc_a['filename']}' and '{doc_b['filename']}' have equal authority and the same date, "
        "so this cannot be resolved automatically. Please verify with your faculty."
    )
    return doc_a, reason  # arbitrary pick, but caller must flag uncertainty


def authority_confidence(doc_a: Dict[str, Any], doc_b: Dict[str, Any]) -> str:
    if doc_a["authority_rank"] != doc_b["authority_rank"]:
        return "high"
    if doc_a["upload_date"] != doc_b["upload_date"]:
        return "medium"
    return "low"
