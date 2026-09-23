"""
Microsoft Foundry LLM abstraction.

`FoundryClient.generate()` is the single choke point every feature uses to
turn retrieved evidence into natural language. Two backends implement the
same contract:

  - "foundry"        : real call to a Microsoft Foundry / Azure AI chat
                        completions deployment (used when FOUNDRY_ENDPOINT +
                        FOUNDRY_API_KEY are set and FORCE_LOCAL_MODE=false).
  - "local_template"  : a deterministic, fully offline generator that
                        composes answers strictly from the evidence it is
                        given (extractive + light templating). It NEVER
                        invents facts that are not in the provided context,
                        which is exactly the anti-hallucination behaviour
                        this project requires, and it means the whole demo
                        runs with zero API keys.

Every response records which backend produced it (`source`) so the UI can
show students an honest "Grounded via local engine / Foundry" indicator.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import re

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("foundry_client")


@dataclass
class LLMResult:
    text: str
    source: str  # "foundry" | "local_template"


class FoundryClient:
    def __init__(self):
        self.use_foundry = settings.HAS_FOUNDRY_LLM
        if self.use_foundry:
            import httpx
            self._client = httpx.Client(timeout=30)

    def generate(self, system_prompt: str, user_prompt: str, context: str = "", max_tokens: int = 600) -> LLMResult:
        if self.use_foundry:
            try:
                return self._generate_foundry(system_prompt, user_prompt, context, max_tokens)
            except Exception as e:  # pragma: no cover - network dependent
                log.warning(f"Foundry chat completion failed ({e}); using local template engine")
        return self._generate_local(system_prompt, user_prompt, context)

    @staticmethod
    def _is_reasoning_model(model_name: str) -> bool:
        """
        GPT-5-family and o-series ("reasoning") models use a different request
        shape than classic chat models: they require `max_completion_tokens`
        instead of `max_tokens`, and reject any `temperature` other than the
        default (1) - sending temperature=0.2 causes a 400 error on these
        models. Older models (gpt-4o-mini, gpt-4.1, etc.) still expect the
        classic `max_tokens` + `temperature` shape, so we branch on the
        deployment/model name.
        """
        name = model_name.lower()
        return name.startswith("gpt-5") or name.startswith(("o1", "o3", "o4"))

    # ---- real Microsoft Foundry backend ----
    def _generate_foundry(self, system_prompt, user_prompt, context, max_tokens) -> LLMResult:
        url = f"{settings.FOUNDRY_ENDPOINT}/chat/completions?api-version={settings.FOUNDRY_API_VERSION}"
        headers = {"api-key": settings.FOUNDRY_API_KEY, "Content-Type": "application/json"}
        full_user = f"Context (retrieved study material):\n{context}\n\nQuestion: {user_prompt}" if context else user_prompt
        payload = {
            "model": settings.FOUNDRY_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_user},
            ],
        }
        if self._is_reasoning_model(settings.FOUNDRY_MODEL):
            # gpt-5 / gpt-5-mini / o-series: no custom temperature, different token-limit key
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens
            payload["temperature"] = 0.2
        resp = self._client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return LLMResult(text=text.strip(), source="foundry")

    # ---- local, offline, non-hallucinating fallback ----
    def _generate_local(self, system_prompt, user_prompt, context) -> LLMResult:
        if not context.strip():
            text = (
                "I couldn't find this information in your study material.\n\n"
                "General knowledge (not verified against your documents): "
                + _local_general_knowledge_stub(user_prompt)
            )
            return LLMResult(text=text, source="local_template")

        sentences = _split_sentences(context)
        ranked = _rank_sentences_by_overlap(sentences, user_prompt)
        top = ranked[:4] if ranked else sentences[:3]

        simplify = "beginner" in user_prompt.lower() or "simple" in user_prompt.lower() or "eli5" in user_prompt.lower()
        body = " ".join(top)
        if simplify:
            body = _simplify(body)

        return LLMResult(text=body.strip(), source="local_template")


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [p.strip() for p in parts if len(p.strip()) > 15]


def _rank_sentences_by_overlap(sentences: List[str], query: str) -> List[str]:
    q_terms = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
    scored = []
    for s in sentences:
        s_terms = set(re.findall(r"[a-zA-Z0-9]+", s.lower()))
        overlap = len(q_terms & s_terms)
        scored.append((overlap, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for score, s in scored if score > 0] or [s for _, s in scored]


def _simplify(text: str) -> str:
    # very light heuristic simplification: shorter sentences, plain lead-in
    text = re.sub(r";", ".", text)
    return "In simple terms: " + text


def _local_general_knowledge_stub(query: str) -> str:
    return (
        f"This looks like a general question about \"{query.strip('?')}\". "
        "Try rephrasing it around a topic in your syllabus, or upload the relevant "
        "document so I can ground the answer in your own study material."
    )


_client: Optional[FoundryClient] = None


def get_foundry_client() -> FoundryClient:
    global _client
    if _client is None:
        _client = FoundryClient()
    return _client
