"""
Vector store / hybrid retrieval layer.

This plays the role that Azure AI Search + Foundry IQ's knowledge index
would play in production (see README "Where Foundry IQ / AI Search would
plug in"). It exposes the exact same shape of results (chunk text + rich
metadata + relevance score) so the rest of the pipeline - and a future
swap to real Azure AI Search - stays identical.

Hybrid search = semantic (TF-IDF/Foundry embedding cosine similarity)
                 + lexical keyword overlap boost
This matters for this domain because exact terms ("VLAN", "CRC", "MAC
address") carry most of the meaning, so pure dense retrieval alone under-
performs a hybrid approach - which is exactly what Azure AI Search's
hybrid mode does in production.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
import re
import numpy as np

from app.db import get_all_chunks
from app.core.embeddings import get_embedding_provider
from app.utils.logger import get_logger

log = get_logger("vector_store")

# Minimum hybrid relevance score for a chunk to be considered "actually
# relevant" rather than just the least-irrelevant thing in the index.
# Below this, the agent treats the query as unanswerable from documents
# and falls back to a clearly-labeled general-knowledge response instead
# of presenting an unrelated chunk as if it were grounded.
MIN_RELEVANCE_SCORE = 0.08


class VectorStore:
    def __init__(self):
        self.provider = get_embedding_provider()
        self.chunks: List[Dict[str, Any]] = []
        self.matrix: Optional[np.ndarray] = None

    def build(self):
        """(Re)build the index from everything currently in the database."""
        self.chunks = get_all_chunks()
        texts = [c["text"] for c in self.chunks]
        self.provider.fit(texts)
        self.matrix = self.provider.transform(texts) if texts else None
        log.info(f"Vector index built: {len(self.chunks)} chunks, provider={self.provider.name}")

    def is_empty(self) -> bool:
        return not self.chunks

    def search(
        self,
        query: str,
        top_k: int = 6,
        subject: Optional[str] = None,
        doc_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if self.is_empty():
            return []

        query_vec = self.provider.transform([query])
        sims = _cosine_sim(query_vec, self.matrix)[0]

        query_terms = set(_tokenize(query))
        results = []
        for i, chunk in enumerate(self.chunks):
            if subject and chunk["subject"].lower() != subject.lower():
                continue
            if doc_types and chunk["doc_type"] not in doc_types:
                continue

            semantic_score = float(sims[i])
            chunk_terms = set(_tokenize(chunk["text"]))
            overlap = len(query_terms & chunk_terms)
            keyword_score = overlap / max(len(query_terms), 1)

            # Hybrid score: weighted blend, tunable
            hybrid_score = 0.65 * semantic_score + 0.35 * keyword_score

            results.append({**chunk, "score": round(hybrid_score, 4)})

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    def search_by_topic(self, topic: str, subject: Optional[str] = None, top_k: int = 10):
        return self.search(topic, top_k=top_k, subject=subject)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if b is None or b.shape[0] == 0:
        return np.zeros((a.shape[0], 0))
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    return a_norm @ b_norm.T


_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
        _store.build()
    return _store


def rebuild_vector_store():
    global _store
    _store = VectorStore()
    _store.build()
    return _store
