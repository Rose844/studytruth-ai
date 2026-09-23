# 🎓 StudyTruth AI — Intelligent Study Assistant

StudyTruth AI is not another "upload a PDF and chat with it" tool. It's a
**Knowledge Conflict Detection + Study Decision Assistant** for college
students whose study material is scattered across syllabi, lecture notes,
faculty PDFs, assignments, PYQs, lab manuals and notices — where old and new
documents sometimes disagree.

> Ask: *"Is VLAN included in my CN syllabus?"*
> StudyTruth AI searches every relevant document, notices that the 2023
> syllabus doesn't mention VLAN while the 2025 syllabus does, resolves the
> disagreement using source authority + recency, and shows you **both
> sources and its reasoning** — never a silent guess.

The dashboard also surfaces **upcoming exam countdowns** (parsed from real
official notices) and **per-subject study progress** (syllabus topics
covered vs. remaining), so it reads like a product a student would actually
open every morning, not a bare chat box.

---

## Table of contents
1. [What makes this different](#what-makes-this-different)
2. [Architecture](#architecture)
3. [Folder structure](#folder-structure)
4. [Tech stack](#tech-stack)
5. [Setup & running locally](#setup--running-locally)
6. [Environment variables](#environment-variables)
7. [Demo flow (copy-paste script)](#demo-flow)
8. [Where Microsoft Foundry / Foundry IQ / AI Search plug in](#microsoft-foundry-mapping)
9. [RAG pipeline details](#rag-pipeline-details)
10. [The Study Agent & tools](#the-study-agent--tools)
11. [Anti-hallucination guarantees](#anti-hallucination-guarantees)
12. [Testing](#testing)
13. [Known simplifications](#known-simplifications--future-work)

---

## What makes this different

| Generic RAG chatbot | StudyTruth AI |
|---|---|
| Retrieves chunks, answers | Retrieves chunks **from every relevant document**, cross-checks them |
| Assumes documents agree | Actively looks for **contradictions** across versions/sources |
| Trusts whichever chunk ranks highest | Ranks **source authority** (syllabus > faculty material > notes > assignments > PYQs) and **recency**, and explains the choice |
| One-shot Q&A | An **agent** that picks from 8 tools depending on intent: search, compare, detect conflicts, find PYQs, generate quizzes, build study plans, summarize |
| Silent about uncertainty | Explicitly says *"I couldn't find this in your documents"* or *"this can't be resolved automatically — verify with faculty"* |

---

## Architecture

**Ask AI / general query path**

```
Student
  ↓
Frontend (dashboard, chat UI)
  ↓
FastAPI  →  Study Agent (intent detection)
  ↓
Agent decides which tool(s) to call
  ↓
Hybrid Retrieval (semantic + keyword) over the Vector Store
  ↓
Relevant chunks + metadata (subject, type, date, version, authority)
  ↓
Foundry LLM (or local grounded template engine)
  ↓
Grounded answer + citations + confidence
  ↓
Frontend renders answer, sources, and any conflict warning
```

**Conflict detection path**

```
Documents (syllabus, notes, PYQs, ...)
  ↓
Document metadata (type, date, version, authority rank)
  ↓
Retrieval: find every document that touches the topic
  ↓
Split into "mentions it" vs "silent about it" / differing unit placement
  ↓
Comparison Agent (conflict_detector.py)
  ↓
Source Authority engine: rank comparison → recency comparison → explain
  ↓
Final structured conflict: statement A, statement B, resolution, confidence
```

---

## Folder structure

```
studytruth-ai/
├── README.md                     ← you are here
├── run.py                        ← one-command launcher (backend + frontend + seed + browser)
├── run.bat / run.sh               double-click wrappers for run.py (Windows / Mac-Linux)
├── .env.example                  ← copy to .env, no secrets committed
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                     FastAPI app + startup (builds vector index)
│   │   ├── config.py                   env-driven settings, cloud/local mode switch
│   │   ├── db.py                       SQLite persistence (documents, chunks, quizzes, progress)
│   │   ├── models/schemas.py           Pydantic request/response models, authority ranks
│   │   ├── core/
│   │   │   ├── document_processor.py   extraction, chunking, topic tagging
│   │   │   ├── embeddings.py           EmbeddingProvider: local TF-IDF ↔ Foundry embeddings
│   │   │   ├── vector_store.py         hybrid (semantic+keyword) retrieval
│   │   │   ├── foundry_client.py       LLM abstraction: Foundry chat ↔ local grounded engine
│   │   │   ├── source_authority.py     authority + recency conflict resolution
│   │   │   ├── conflict_detector.py    THE signature feature: conflict detection + doc diff
│   │   │   ├── tools.py                8 agent tools (search, quiz, study plan, PYQs, ...)
│   │   │   └── agent.py                intent routing + grounded answer assembly
│   │   └── routers/                    documents, ask, conflicts, exam, quiz, analytics
│   ├── data/{uploads,storage}/         uploaded files + sqlite db + vector index (gitignored)
│   └── tests/test_api.py               14 end-to-end tests incl. the VLAN conflict demo
├── frontend/
│   ├── index.html                      dashboard shell (sidebar + 7 pages)
│   ├── css/styles.css                  design system (tokens, cards, chat UI, diff view)
│   └── js/                             api.js, helpers.js, app.js + one module per page
├── sample_data/                        realistic CN / DNN / DSA syllabi, notes, PYQs, labs, notices
│   └── computer_networks/syllabus_2025_v2.txt vs syllabus_2023_v1.txt ← intentional VLAN conflict
└── scripts/seed_data.py                loads all sample_data into the database
```

---

## Tech stack

- **Backend**: Python, FastAPI, SQLite (zero external DB setup needed), scikit-learn (TF-IDF embeddings), pypdf (PDF extraction)
- **Frontend**: Vanilla HTML/CSS/JS (no build step — open a browser and go), Manrope + Source Serif 4 typography
- **AI layer**: Microsoft Foundry-compatible LLM abstraction with a fully offline local fallback (see below)
- **Retrieval**: Custom hybrid vector store today; designed as a drop-in replacement for Azure AI Search / Foundry IQ

We chose this stack deliberately: **the whole product works with zero API
keys and zero internet access**, so it can be graded, demoed, or extended
anywhere — while every integration point with Microsoft Foundry / Foundry IQ
/ Azure AI Search is a clean, documented abstraction ready for real
credentials.

---

## Setup & running locally

### Option A — one command (recommended)

```bash
cd studytruth-ai
python run.py
```

This single command creates `.env` if missing, seeds the sample data on
first run, starts the backend (port 8000) and frontend (port 5500)
together, and opens your browser automatically. Press `Ctrl+C` to stop
both servers. On Windows you can also just double-click `run.bat`; on
Mac/Linux, `./run.sh`.

(You still need to `pip install -r backend/requirements.txt` once before
the first run — see Option B below if you haven't done that yet.)

### Option B — manual, two terminals

### 1. Backend

```bash
cd studytruth-ai
cp .env.example .env          # defaults to local mock mode - no keys needed
cd backend
python3 -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt

# Seed realistic sample data (Computer Networks, DNN, DSA + the VLAN conflict pair)
cd ..
python3 scripts/seed_data.py

# Start the API
cd backend
uvicorn app.main:app --reload --port 8000
```

Backend is now live at `http://localhost:8000` (interactive docs at `/docs`).

### 2. Frontend

In a second terminal:

```bash
cd studytruth-ai/frontend
python3 -m http.server 5500
```

Open `http://localhost:5500` in your browser. The frontend calls the
backend at `http://localhost:8000` by default — change
`window.STUDYTRUTH_API_BASE` at the top of `index.html` if you run the API
elsewhere.

### 3. Run tests

```bash
cd studytruth-ai/backend
pytest tests/ -v
```

---

## Environment variables

See `.env.example` for the full list with comments. Summary:

| Variable | Purpose | If empty |
|---|---|---|
| `FOUNDRY_ENDPOINT`, `FOUNDRY_API_KEY`, `FOUNDRY_MODEL` | Microsoft Foundry chat + embeddings deployment | Falls back to local TF-IDF embeddings + local grounded template engine |
| `FOUNDRY_IQ_ENABLED`, `FOUNDRY_IQ_KNOWLEDGE_SOURCE` | Marks where Foundry IQ's managed knowledge index would connect | Local vector store plays this role instead |
| `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`, `AZURE_SEARCH_INDEX` | Microsoft AI Search retrieval | Local hybrid vector store plays this role instead |
| `FORCE_LOCAL_MODE` | Forces offline mode even if keys are set (default `true`, so the project runs out of the box) | — |

**No secrets are hardcoded anywhere in the code.** Set `FORCE_LOCAL_MODE=false`
and fill in real Foundry credentials to switch the exact same pipeline over
to cloud-backed retrieval/generation with no other code changes.

---

## Demo flow

Run these in the **Ask AI** page after seeding sample data (or via `curl`
against `/api/ask`):

**1. Knowledge Conflict Detection**
> "Is VLAN included in my CN syllabus?"

→ Detects that the 2025-26 syllabus lists VLAN under Unit 3 while the
2023-24 syllabus doesn't mention it at all; resolves using recency +
authority; shows both source snippets with dates and versions.

**2. Exam Preparation Mode**
> "Make a revision plan for tomorrow." *(subject: Computer Networks)*

→ Builds a prioritized list of every syllabus topic, ranked by how often
each one appears in previous year question papers, flags topics missing
lecture notes.

**3. Syllabus diff**
> "I have two syllabi. What changed?"

→ Compares the two CN syllabus versions: **Added** (VLAN, Wireless LAN),
**Removed** (none), **Modified** (topics that moved to a different unit).

**4. Conflict resolution with explicit reasoning**
> "These two documents say different things. Which one should I follow?"

→ Explains *why* the newer syllabus is treated as authoritative (same
document type, more recent date) rather than silently picking one.

Other things to try: *"Give me 5 MCQs on VLAN"*, *"Explain VLAN like I'm a
beginner"*, *"Give me PYQs related to checksum"*, *"Test me on Computer
Networks"*.

---

## Microsoft Foundry mapping

This project is built around clean abstractions so that swapping in real
Microsoft Foundry services is a **configuration change, not a rewrite**:

- **Microsoft Foundry (model access / agent orchestration)**
  `backend/app/core/foundry_client.py` defines `FoundryClient.generate()`
  as the single choke point for turning retrieved evidence into natural
  language. With `FOUNDRY_ENDPOINT` + `FOUNDRY_API_KEY` set (and
  `FORCE_LOCAL_MODE=false`), it calls a real Foundry chat-completions
  deployment. Without credentials, it uses a deterministic, fully offline
  extractive/template engine that **never invents facts outside the
  retrieved context** — which doubles as a strong anti-hallucination
  baseline even when running against a real LLM.

- **Microsoft Foundry IQ (managed knowledge / RAG layer)**
  Foundry IQ's job is to host a managed, versioned knowledge index built
  from an org's documents and expose grounded retrieval to agents. In this
  project, `backend/app/core/vector_store.py` plays that exact role
  locally: it ingests the same per-document metadata (subject, doc type,
  date, version, authority rank) that a Foundry IQ knowledge source would
  carry, and exposes the same shape of result (chunk + metadata + score)
  that a Foundry IQ-backed retrieval tool would return to the agent. Set
  `FOUNDRY_IQ_ENABLED=true` and point `FOUNDRY_IQ_KNOWLEDGE_SOURCE` at a
  real Foundry IQ knowledge source, then swap `VectorStore.search()`'s
  implementation for a call to that knowledge source — `agent.py` and
  every tool in `tools.py` call `search_documents()` / `retrieve_topic()`
  without caring which backend answers, so nothing downstream changes.

- **Microsoft AI Search (retrieval)**
  `backend/app/core/embeddings.py` includes `FoundryEmbeddingProvider`,
  which calls a Foundry-hosted embeddings deployment over HTTPS. Pairing
  real embeddings with an Azure AI Search index (`AZURE_SEARCH_*` env vars)
  would replace the local cosine-similarity search in `vector_store.py`
  with a call to Azure AI Search's hybrid search API — same hybrid
  semantic+keyword behaviour, cloud-hosted instead of in-process.

- **Agents and tool/function calling**
  `backend/app/core/agent.py` implements the agent loop: intent detection
  → tool selection → tool execution → grounded answer assembly, with every
  step logged to `reasoning_trace` so it's visible in the UI. It currently
  uses transparent keyword-based intent detection so the whole thing runs
  without any LLM at all; the same tool registry
  (`search_documents`, `retrieve_topic`, `compare_documents`,
  `detect_conflicts`, `find_pyqs`, `generate_quiz`, `create_study_plan`,
  `summarize_topic`) is exactly what you'd hand to a real Foundry agent's
  function-calling configuration — only `_detect_intent()` would change.

- **Evaluation / monitoring**
  `app/db.py`'s `chat_log`, `quiz_log` and `topic_progress` tables capture
  every question asked, whether it was grounded, and quiz accuracy per
  topic — the same signal a Foundry evaluation pipeline would consume to
  track groundedness and answer quality over time.

---

## RAG pipeline details

1. **Ingestion** (`document_processor.py`): extracts text (PDF via `pypdf`,
   or plain text), chunks with paragraph-aware boundaries (900 chars,
   150 overlap), and auto-tags topics from a small controlled vocabulary
   per subject.
2. **Metadata** stored per document: `subject`, `doc_type`,
   `academic_year`, `version`, `upload_date`, `topic_tags`,
   `authority_rank`.
3. **Embeddings** (`embeddings.py`): local TF-IDF (word 1-2 grams) by
   default — a real, working vector space that needs no internet — or
   Foundry-hosted embeddings when configured.
4. **Hybrid retrieval** (`vector_store.py`): blends semantic cosine
   similarity (65%) with lexical keyword overlap (35%), because exact
   terms ("VLAN", "CRC") carry most of the meaning in this domain — this
   mirrors Azure AI Search's hybrid search mode.
5. **Context construction**: top-k chunks (default 6) are assembled into
   context for the LLM/template engine, always carrying their source
   metadata forward.
6. **Grounded generation**: `foundry_client.py` only uses the supplied
   context; if no relevant chunks are found, it says so explicitly rather
   than generating from parametric knowledge.
7. **Citations**: every response includes `filename`, `doc_type`,
   `subject`, `version`, `upload_date`, `authority_rank`, `snippet`, and
   a relevance `score`, so answers are always traceable to source
   documents.

---

## The Study Agent & tools

`agent.py` routes each query to one of 8 tools based on detected intent:

| Tool | Used for |
|---|---|
| `search_documents` | Default "Ask My Study Material" queries |
| `retrieve_topic` | Topic-scoped retrieval used by other tools |
| `compare_documents` | "What changed between these syllabi?" |
| `detect_conflicts` | "Which one should I follow?" / contradiction checks |
| `find_pyqs` | "Give me PYQs related to X" |
| `generate_quiz` | "Give me 10 MCQs" / "Test me on X" |
| `create_study_plan` | "What should I study for my exam?" |
| `summarize_topic` | "What is X?" / "Explain like I'm a beginner" |

Every response includes a `reasoning_trace` (visible in the UI under
"Agent reasoning") showing which tool(s) were called and why — including
the fact that the agent **proactively checks for conflicts** on the
detected topic even for plain search queries, which is how the VLAN demo
surfaces a conflict warning from a query that didn't explicitly ask for one.

---

## Anti-hallucination guarantees

- If no relevant chunks are retrieved, the answer literally starts with
  *"I couldn't find this information in your study material."* and any
  further explanation is clearly labeled *"General knowledge (not verified
  against your documents)"* — both in the API payload (`ai_generated_note`)
  and in the UI (amber warning banner).
- The local template engine only ever recombines sentences that exist in
  the retrieved context — it cannot introduce new facts.
- Conflicting information is **never** silently resolved: the API always
  returns both statements, both sources with metadata, and an explicit
  `resolution` string. When authority and recency are genuinely tied,
  `confidence` is `"low"` and the UI shows *"Unresolved — verify with
  faculty"* instead of guessing.

---

## Adding a brand-new subject (no code changes needed)

You are **not** limited to Computer Networks / DNN / DSA. Upload a syllabus
for any subject — type any name into the Subject field in **My Documents**
— and StudyTruth AI automatically learns that subject's topics from the
document's own structure:

- It looks for `UNIT n: ...` / `Module n: ...` headings in syllabi and
  splits the comma-separated topic list that follows each one.
- It looks for `Lecture n: <title>` headings in notes and uses each title
  as a topic directly.
- Learned topics are stored per-subject in the `subject_topics` table and
  combined with the (optional) hardcoded seed list in
  `document_processor.py`'s `TOPIC_VOCAB` — which exists only as an
  accuracy boost for the 3 bundled demo subjects, not a requirement.

Once a syllabus is uploaded, **Study Plan, Ask AI, and Quiz Mode all work
immediately** for that subject — no code edits, no restart. See
`test_new_subject_works_with_zero_configuration` in `tests/test_api.py`
for an automated proof of this.

## Testing

`backend/tests/test_api.py` runs 14 end-to-end tests against the real
pipeline (no mocking) using the sample data, including:
- the VLAN conflict demo resolves to the newer syllabus
- comparing the two CN syllabi correctly lists VLAN as an added topic
- ungrounded questions never claim to be grounded
- quizzes are grounded and structurally valid
- the agent routes quiz / study-plan / compare intents to the right tool

```bash
cd backend && pytest tests/ -v
```

---

## Known simplifications & future work

- Topic vocabulary (`TOPIC_VOCAB` in `document_processor.py`) is a small
  curated list per subject for this MVP; a production version would pull
  this from a Foundry IQ knowledge source's taxonomy or extract it with an
  LLM.
- "Modified topic" detection in the Conflict Checker uses a simple
  "nearest Unit/Module number" heuristic, so unrelated unit renumbering can
  appear alongside genuine content changes — good enough to demonstrate the
  feature, but a production version would diff at the sentence level.
- The local LLM fallback is intentionally extractive/template-based (not a
  small local language model) so the whole project runs with zero
  downloads and zero GPU — swapping in a real Foundry deployment is a
  `.env` change away.
- Authentication/multi-user accounts are out of scope for this MVP; all
  data is stored in a single local SQLite file.
