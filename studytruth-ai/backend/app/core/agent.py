"""
The Study Agent.

This is the "Agentic AI" piece the brief asks for: given a free-text
student query, the agent (1) detects intent, (2) decides which tool(s) from
its toolbox to call, (3) calls them, and (4) assembles a grounded, cited
answer - proactively running Knowledge Conflict Detection whenever the
query touches a topic that has conflicting coverage across documents.

Tool registry:
  search_documents, retrieve_topic, compare_documents, detect_conflicts,
  find_pyqs, generate_quiz, create_study_plan, summarize_topic

Intent detection is rule/keyword based (transparent and dependency-free).
When real Foundry credentials are present it would be equally valid to
replace `_detect_intent` with a Foundry function-calling request - the
tool registry and downstream code would not need to change.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional

from app.core import tools
from app.core.vector_store import MIN_RELEVANCE_SCORE
from app.core.conflict_detector import detect_conflicts_for_topic, compare_documents
from app.core.foundry_client import get_foundry_client
from app.core.document_processor import get_topic_vocab_for_subject
from app.db import get_all_documents, log_chat

INTENT_PATTERNS = [
    ("generate_quiz", [r"\bmcqs?\b", r"\bquiz\b", r"test me", r"practice questions?"]),
    ("create_study_plan", [r"revision plan", r"study plan", r"what should i study", r"prepare for", r"exam tomorrow"]),
    ("compare_documents", [r"compare", r"what changed", r"what('s| is) (the )?difference"]),
    ("detect_conflicts", [r"conflict", r"contradiction", r"which (one|source) should i follow", r"different things", r"disagree"]),
    ("find_pyqs", [r"\bpyqs?\b", r"previous year", r"past (paper|question)"]),
    ("summarize_topic", [r"^what is\b", r"^explain\b", r"summar(y|ize)", r"like i'?m a beginner", r"eli5"]),
]


def _detect_intent(query: str) -> str:
    q = query.lower().strip()
    for intent, patterns in INTENT_PATTERNS:
        for p in patterns:
            if re.search(p, q):
                return intent
    return "search_documents"


def _extract_topic(query: str, subject: Optional[str]) -> Optional[str]:
    q = query.lower()
    if subject:
        candidates = get_topic_vocab_for_subject(subject)
    else:
        # no subject given: pool topics across every subject that has documents
        candidates = []
        for s in {d["subject"] for d in get_all_documents()}:
            candidates.extend(get_topic_vocab_for_subject(s))
    # prefer the longest matching vocab term (e.g. "network security" over "security")
    matches = [t for t in candidates if t in q]
    if matches:
        return max(matches, key=len)
    # fallback: strip common question words and use the remainder as a topic guess
    cleaned = re.sub(r"\b(what is|explain|define|is|the|a|an|in|my|for|of|included|about)\b", " ", q)
    cleaned = re.sub(r"[?.!]", "", cleaned).strip()
    return cleaned if cleaned else None


def _extract_subject(query: str, provided: Optional[str]) -> Optional[str]:
    if provided:
        return provided
    q = query.lower()
    if re.search(r"\bcn\b|computer network", q):
        return "computer networks"
    if re.search(r"\bdnn\b|deep neural|neural network", q):
        return "deep neural networks"
    if re.search(r"\bdsa\b|data structure|algorithm", q):
        return "data structures and algorithms"
    return None


def handle_query(query: str, subject: Optional[str] = None, completed_topics: Optional[List[str]] = None) -> Dict[str, Any]:
    trace: List[str] = []
    subject = _extract_subject(query, subject)
    intent = _detect_intent(query)
    trace.append(f"Detected intent: '{intent}'" + (f" (subject: {subject})" if subject else ""))

    if intent == "generate_quiz":
        topic = _extract_topic(query, subject) or "general"
        trace.append(f"Calling tool generate_quiz(topic='{topic}')")
        result = tools.generate_quiz(topic, subject=subject, num_questions=5)
        answer = (
            f"Here are {len(result['questions'])} grounded practice questions on '{topic}'."
            if result["grounded"] else
            "I couldn't find enough material on this topic to build a grounded quiz yet."
        )
        response = _wrap(answer, [], intent, trace, extra={"quiz": result}, grounded_override=result["grounded"])

    elif intent == "create_study_plan":
        if not subject:
            trace.append("No subject detected - asking the student to specify one.")
            response = _wrap(
                "Which subject should I build your revision plan for? (e.g. Computer Networks, DSA, Deep Neural Networks)",
                [], intent, trace,
            )
        else:
            trace.append(f"Calling tool create_study_plan(subject='{subject}')")
            plan = tools.create_study_plan(subject, completed_topics=completed_topics)
            response = _wrap(plan["summary"], [], intent, trace, extra={"study_plan": plan},
                              grounded_override=plan["total_topics"] > 0)

    elif intent == "compare_documents":
        docs = [d for d in get_all_documents() if (not subject or d["subject"].lower() == subject.lower())
                and d["doc_type"] == "syllabus"]
        docs.sort(key=lambda d: d["upload_date"], reverse=True)
        if len(docs) < 2:
            trace.append("Fewer than 2 syllabus versions found - cannot compare.")
            response = _wrap("I only have one syllabus version for this subject, so there's nothing to compare yet. Upload an older version to compare.", [], intent, trace)
        else:
            trace.append(f"Comparing '{docs[0]['filename']}' vs '{docs[1]['filename']}'")
            cmp = compare_documents(docs[0]["doc_id"], docs[1]["doc_id"])
            response = _wrap(cmp["explanation"], [], intent, trace, extra={"comparison": cmp}, grounded_override=True)

    elif intent == "detect_conflicts":
        topic = _extract_topic(query, subject)
        trace.append(f"Calling tool detect_conflicts(topic='{topic}', subject='{subject}')")
        conflicts = detect_conflicts_for_topic(topic, subject=subject) if topic else []
        if conflicts:
            answer = _explain_conflicts(topic, conflicts)
            response = _wrap(answer, [], intent, trace, conflicts=conflicts)
        else:
            trace.append("No structured conflicts found - falling back to grounded search.")
            response = _search_and_answer(query, subject, trace, intent="detect_conflicts")

    elif intent == "find_pyqs":
        topic = _extract_topic(query, subject) or query
        trace.append(f"Calling tool find_pyqs(topic='{topic}')")
        raw_chunks = tools.find_pyqs(topic, subject=subject)
        chunks = [c for c in raw_chunks if c["score"] >= MIN_RELEVANCE_SCORE]
        if not chunks:
            response = _wrap("I couldn't find this information in your study material. No previous year questions matched this topic yet.", [], intent, trace)
        else:
            answer = f"Found {len(chunks)} previous-year question excerpt(s) related to '{topic}'."
            response = _wrap(answer, chunks, intent, trace)

    elif intent == "summarize_topic":
        topic = _extract_topic(query, subject) or query
        simplify = "beginner" in query.lower() or "simple" in query.lower() or "eli5" in query.lower()
        trace.append(f"Calling tool summarize_topic(topic='{topic}', simplify={simplify})")
        result = tools.summarize_topic(topic, subject=subject, simplify=simplify)
        if not result["grounded"]:
            response = _wrap(
                "I couldn't find this information in your study material.\n\n"
                f"General knowledge (not verified against your documents): '{topic}' is a topic you may want to "
                "upload material for so I can give you a grounded, cited explanation.",
                [], intent, trace, note="general_knowledge_fallback",
            )
        else:
            response = _wrap(result["text"], result["citations"], intent, trace)

    else:  # search_documents - default "Ask My Study Material" path, conflict-aware
        response = _search_and_answer(query, subject, trace, intent="search_documents")

    log_chat(query, response["tool_used"], response["grounded"])
    return response


def _search_and_answer(query: str, subject: Optional[str], trace: List[str], intent: str) -> Dict[str, Any]:
    topic = _extract_topic(query, subject)
    trace.append(f"Calling tool search_documents(query='{query}', subject='{subject}')")
    raw_chunks = tools.search_documents(query, subject=subject, top_k=6)
    chunks = [c for c in raw_chunks if c["score"] >= MIN_RELEVANCE_SCORE]
    if raw_chunks and not chunks:
        trace.append(f"Top match scored below relevance threshold ({raw_chunks[0]['score']:.3f} < {MIN_RELEVANCE_SCORE}) - treating as not found")

    conflicts = []
    if topic:
        trace.append(f"Proactively checking detect_conflicts(topic='{topic}') before answering")
        conflicts = detect_conflicts_for_topic(topic, subject=subject)

    if not chunks and not conflicts:
        trace.append("No relevant chunks found in study material.")
        client = get_foundry_client()
        result = client.generate(
            system_prompt="Answer briefly and clearly label this as general knowledge, not from the student's documents.",
            user_prompt=query, context="",
        )
        return _wrap(result.text, [], intent, trace, note="general_knowledge_fallback")

    if conflicts:
        answer = _explain_conflicts(topic, conflicts)
        # still attach the strongest supporting citation for context
        top_citation = [conflicts[0]["doc_a"]]
        return _wrap(answer, top_citation, intent, trace, conflicts=conflicts)

    trace.append(f"Retrieved {len(chunks)} chunks; generating grounded answer")
    context = "\n\n".join(c["text"] for c in chunks[:4])
    client = get_foundry_client()
    result = client.generate(
        system_prompt="You are StudyTruth AI, a grounded study assistant. Only use the given context. Never invent facts not present in it.",
        user_prompt=query, context=context,
    )
    return _wrap(result.text, chunks, intent, trace)


def _display_topic(topic: str) -> str:
    return topic.upper() if len(topic) <= 5 and topic.isalpha() else topic.title()


def _explain_conflicts(topic: str, conflicts: List[Dict[str, Any]]) -> str:
    c = conflicts[0]
    lines = [f"Here's what your documents say about **{_display_topic(topic)}** - and where they disagree:\n"]
    lines.append("Evidence:")
    lines.append(f"• {c['statement_a']}")
    lines.append(f"• {c['statement_b']}")
    lines.append("")
    if c["confidence"] == "low":
        lines.append(f"⚠️ I can't fully resolve this automatically: {c['resolution']}")
    else:
        lines.append(c["resolution"])
    return "\n".join(lines)


def _wrap(answer: str, chunks: List[Dict[str, Any]], intent: str, trace: List[str],
          conflicts: Optional[List[Dict[str, Any]]] = None, note: Optional[str] = None,
          extra: Optional[Dict[str, Any]] = None, grounded_override: Optional[bool] = None) -> Dict[str, Any]:
    citations = []
    for c in chunks:
        if "snippet" in c:
            # already a formatted citation (e.g. produced by conflict_detector)
            citations.append(c)
        else:
            citations.append({
                "doc_id": c["doc_id"], "filename": c["filename"], "doc_type": c["doc_type"],
                "subject": c["subject"], "version": c.get("version", ""), "upload_date": c["upload_date"],
                "authority_rank": c["authority_rank"],
                "snippet": c["text"][:220].strip() + ("..." if len(c["text"]) > 220 else ""),
                "score": c.get("score", 1.0),
            })
    grounded = bool(citations) or bool(conflicts) if grounded_override is None else grounded_override
    if not grounded:
        confidence = "none"
    else:
        top_score = max((c["score"] for c in citations), default=1.0)
        confidence = "high" if top_score >= 0.35 or conflicts else ("medium" if top_score >= 0.12 else "low")

    out = {
        "answer": answer,
        "grounded": grounded,
        "confidence": confidence,
        "citations": citations,
        "conflicts": [
            {
                "topic": c["topic"], "doc_a": c["doc_a"], "doc_b": c["doc_b"],
                "statement_a": c["statement_a"], "statement_b": c["statement_b"],
                "resolution": c["resolution"], "chosen_doc_id": c["chosen_doc_id"],
                "confidence": c["confidence"],
            } for c in (conflicts or [])
        ],
        "ai_generated_note": "This part of the answer is general knowledge, not verified against your uploaded documents." if note == "general_knowledge_fallback" else None,
        "tool_used": intent,
        "reasoning_trace": trace,
    }
    if extra:
        out.update(extra)
    return out
