"""
Concrete implementations of every tool the Study Agent can call:

  search_documents   - hybrid retrieval over all study material
  retrieve_topic      - retrieval scoped/boosted to one topic
  compare_documents   - delegates to conflict_detector (Added/Removed/Modified)
  detect_conflicts    - delegates to conflict_detector (contradiction + resolution)
  find_pyqs           - retrieval scoped to doc_type == pyq
  generate_quiz       - builds grounded MCQs from retrieved evidence
  create_study_plan   - prioritized revision plan using topic frequency + gaps
  summarize_topic     - extractive summary + optional "explain simply" mode

Every tool returns citations so the agent/orchestrator can always show
"why" an answer was produced.
"""
from __future__ import annotations
import random
import re
from typing import List, Dict, Any, Optional

from app.core.vector_store import get_vector_store, MIN_RELEVANCE_SCORE
from app.core.foundry_client import get_foundry_client
from app.core.document_processor import get_topic_vocab_for_subject
from app.core.source_authority import compare_authority
from app.db import get_all_documents, get_all_chunks


def search_documents(query: str, subject: Optional[str] = None, top_k: int = 6) -> List[Dict[str, Any]]:
    store = get_vector_store()
    return store.search(query, top_k=top_k, subject=subject)


def retrieve_topic(topic: str, subject: Optional[str] = None, top_k: int = 8) -> List[Dict[str, Any]]:
    store = get_vector_store()
    return store.search_by_topic(topic, subject=subject, top_k=top_k)


def find_pyqs(topic: str, subject: Optional[str] = None, top_k: int = 8) -> List[Dict[str, Any]]:
    store = get_vector_store()
    return store.search(topic, subject=subject, doc_types=["pyq"], top_k=top_k)


def summarize_topic(topic: str, subject: Optional[str] = None, simplify: bool = False) -> Dict[str, Any]:
    raw_chunks = retrieve_topic(topic, subject=subject, top_k=6)
    chunks = [c for c in raw_chunks if c["score"] >= MIN_RELEVANCE_SCORE]
    if not chunks:
        return {"grounded": False, "text": None, "citations": []}

    context = "\n\n".join(c["text"] for c in chunks[:4])
    client = get_foundry_client()
    prompt = f"Explain '{topic}' clearly for a college student." + (" Use very simple beginner-friendly language." if simplify else "")
    result = client.generate(
        system_prompt="You are a grounded study assistant. Only use the provided context. Never invent facts.",
        user_prompt=prompt,
        context=context,
    )
    return {"grounded": True, "text": result.text, "source": result.source, "citations": chunks[:4]}


def generate_quiz(topic: str, subject: Optional[str] = None, num_questions: int = 5) -> Dict[str, Any]:
    chunks = retrieve_topic(topic, subject=subject, top_k=12)
    grounded = bool(chunks)
    questions = []

    sentences = []
    for c in chunks:
        for s in re.split(r"(?<=[.!?])\s+", c["text"].replace("\n", " ")):
            s = s.strip()
            if 40 <= len(s) <= 220 and topic.lower() in s.lower():
                sentences.append((s, c))
    # fall back to any sentence from the retrieved chunks if topic-exact sentences are scarce
    if len(sentences) < num_questions:
        for c in chunks:
            for s in re.split(r"(?<=[.!?])\s+", c["text"].replace("\n", " ")):
                s = s.strip()
                if 40 <= len(s) <= 220:
                    sentences.append((s, c))

    random.shuffle(sentences)
    used_texts = set()
    vocab_pool = _distractor_pool(subject)

    for sentence, chunk in sentences:
        if len(questions) >= num_questions:
            break
        if sentence in used_texts:
            continue
        used_texts.add(sentence)

        blank_target = _pick_keyword(sentence, topic, vocab_pool)
        if not blank_target:
            continue
        question_text = re.sub(re.escape(blank_target), "____", sentence, flags=re.IGNORECASE)
        if question_text == sentence:
            continue

        distractors = _make_distractors(blank_target, vocab_pool)
        options = distractors + [blank_target]
        random.shuffle(options)
        correct_index = options.index(blank_target)

        questions.append({
            "question": question_text,
            "options": options,
            "correct_index": correct_index,
            "explanation": f"The original study material states: \"{sentence}\"",
            "source_doc_id": chunk["doc_id"],
            "topic": topic,
        })

    # If we couldn't build enough fill-in-the-blank items, pad with
    # true statement vs negated statement style questions (still grounded).
    idx = 0
    while len(questions) < min(num_questions, max(3, len(sentences))) and idx < len(sentences):
        sentence, chunk = sentences[idx]
        idx += 1
        if any(q["explanation"].endswith(f'"{sentence}"') for q in questions):
            continue
        negated = _negate_statement(sentence)
        options = [sentence, negated]
        random.shuffle(options)
        correct_index = options.index(sentence)
        questions.append({
            "question": "Which statement is TRUE according to your study material?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"The study material confirms: \"{sentence}\"",
            "source_doc_id": chunk["doc_id"],
            "topic": topic,
        })

    return {"topic": topic, "questions": questions[:num_questions], "grounded": grounded}


def create_study_plan(subject: str, completed_topics: Optional[List[str]] = None) -> Dict[str, Any]:
    completed = {t.lower().strip() for t in (completed_topics or [])}
    vocab = get_topic_vocab_for_subject(subject)
    all_chunks = get_all_chunks()
    subject_chunks = [c for c in all_chunks if c["subject"].lower() == subject.lower()]

    if not vocab or not subject_chunks:
        return {"subject": subject, "plan": [], "summary": "No study material found for this subject yet.",
                "total_topics": 0, "topics_remaining": 0}

    pyq_chunks = [c for c in subject_chunks if c["doc_type"] == "pyq"]
    syllabus_chunks = [c for c in subject_chunks if c["doc_type"] == "syllabus"]
    notes_chunks = [c for c in subject_chunks if c["doc_type"] == "lecture_notes"]

    plan_items = []
    for topic in vocab:
        in_syllabus = any(topic in c["text"].lower() for c in syllabus_chunks)
        if not in_syllabus:
            continue  # only plan around topics actually in the current syllabus
        pyq_freq = sum(c["text"].lower().count(topic) for c in pyq_chunks)
        has_notes = any(topic in c["text"].lower() for c in notes_chunks)
        status = "done" if topic in completed else "not_started"

        if pyq_freq >= 2:
            priority, reason = "high", f"Appears {pyq_freq}x across previous year questions - frequently examined."
        elif pyq_freq == 1:
            priority, reason = "medium", "Has appeared in a previous year question paper."
        else:
            priority, reason = "low", "In the syllabus but not seen in past papers yet."

        if not has_notes:
            reason += " No lecture notes found for it yet - check with faculty."

        source_doc_id = None
        for c in syllabus_chunks:
            if topic in c["text"].lower():
                source_doc_id = c["doc_id"]
                break

        plan_items.append({
            "topic": topic, "priority": priority, "reason": reason,
            "pyq_frequency": pyq_freq, "status": status, "source_doc_id": source_doc_id,
        })

    order = {"high": 0, "medium": 1, "low": 2}
    plan_items.sort(key=lambda t: (t["status"] == "done", order[t["priority"]], -t["pyq_frequency"]))

    remaining = [t for t in plan_items if t["status"] != "done"]
    summary = (
        f"{len(plan_items)} syllabus topics found for {subject}. "
        f"{len(remaining)} remaining to revise, prioritized by exam frequency in previous year papers."
    )
    return {
        "subject": subject, "plan": plan_items, "summary": summary,
        "total_topics": len(plan_items), "topics_remaining": len(remaining),
    }


# ---- small helpers ----
def _distractor_pool(subject: Optional[str]) -> List[str]:
    if subject:
        vocab = get_topic_vocab_for_subject(subject)
        if vocab:
            return vocab
    # no subject given, or subject has no learned/seed topics yet: pool from
    # every subject that currently has documents
    from app.db import get_all_subjects_with_topics
    pool: List[str] = []
    for topics in get_all_subjects_with_topics().values():
        pool.extend(topics)
    return pool


def _pick_keyword(sentence: str, topic: str, pool: List[str]) -> Optional[str]:
    if topic.lower() in sentence.lower():
        # return the exact-cased substring
        match = re.search(re.escape(topic), sentence, flags=re.IGNORECASE)
        return match.group(0) if match else None
    return None


def _make_distractors(correct: str, pool: List[str], n: int = 3) -> List[str]:
    candidates = [t.title() if correct[0].isupper() else t for t in pool if t.lower() != correct.lower()]
    random.shuffle(candidates)
    picks = candidates[:n]
    while len(picks) < n:
        picks.append(f"None of the above ({len(picks)+1})")
    return picks


def _negate_statement(sentence: str) -> str:
    if " is " in sentence:
        return sentence.replace(" is ", " is not ", 1)
    if " are " in sentence:
        return sentence.replace(" are ", " are not ", 1)
    if " was " in sentence:
        return sentence.replace(" was ", " was not ", 1)
    return "This is NOT correct: " + sentence
