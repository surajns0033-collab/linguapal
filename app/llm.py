"""Client for the local open-weight model.

Speaks the OpenAI-compatible chat API that both LM Studio and Ollama expose, so
the open-weight model is a swappable part of the stack rather than a hard
dependency on any one vendor. Only local endpoints are used by default.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import httpx

from .config import settings

# Local servers we auto-detect, in priority order. Both expose the
# OpenAI-compatible /v1 surface, so the same code path drives either one.
_CANDIDATES = [
    "http://localhost:1234/v1",   # LM Studio
    "http://localhost:11434/v1",  # Ollama
]

_detected: tuple[str, str] | None = None

# Some open-weight builds (e.g. Gemma 4) emit an inline reasoning block before the
# answer. It must never reach the learner, so we strip it before parsing. We handle
# three shapes: a closed <thought>...</thought>, a stray closing tag, and an
# *unclosed* <thought> (a truncated generation) whose text runs to the very end.
_THOUGHT_RE = re.compile(r"<thought>.*?</thought>", re.DOTALL | re.IGNORECASE)
_THOUGHT_CLOSE_RE = re.compile(r"</thought>", re.IGNORECASE)
_THOUGHT_OPEN_RE = re.compile(r"<thought>", re.IGNORECASE)


def _strip_thought(raw: str) -> str:
    """Remove inline reasoning so it can never leak into the learner's view."""
    raw = _THOUGHT_RE.sub("", raw)
    # Trim anything tag-shaped that leaked (e.g. an unbalanced closing tag).
    raw = _THOUGHT_CLOSE_RE.sub("", raw)
    # If an opening tag is still present the block was never closed (truncated
    # generation). Keep only the part *after* the last opening tag.
    if _THOUGHT_OPEN_RE.search(raw):
        raw = _THOUGHT_OPEN_RE.split(raw)[-1]
    return raw.strip()


class LLMUnavailable(RuntimeError):
    """Raised when no local open-weight model server can be reached."""


@dataclass
class TutorTurn:
    text: str
    corrections: list[str] = field(default_factory=list)
    vocab: list[dict] = field(default_factory=list)
    raw: str = ""
    latency_ms: int = 0
    tokens: int = 0


def _sections(raw: str) -> dict[str, str]:
    """Split a tutor turn into its REPLY / CORRECTIONS / VOCAB sections.

    Small open-weight models are not always tidy: they may bold the labels, put
    them on one line, or drop the newline before a label. Splitting on the label
    tokens (rather than requiring a preceding newline) keeps the parser working
    across a range of models.
    """
    text = re.sub(r"[*_`]+", "", raw)  # drop markdown emphasis on the labels
    parts = re.split(r"(?i)\b(REPLY|CORRECTIONS|VOCAB)\s*:", text)
    out: dict[str, str] = {}
    # split() yields [lead, LABEL, body, LABEL, body, ...]
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].upper()] = parts[i + 1].strip()
    return out


def _parse(raw: str) -> tuple[str, list[str], list[dict]]:
    """Parse the strict REPLY/CORRECTIONS/VOCAB format the prompt asks for."""
    # Drop any inline reasoning block so it can never leak into the learner's view.
    raw = _strip_thought(raw)
    sections = _sections(raw)
    if not sections:  # no labels at all: treat the whole thing as the reply
        return raw, [], []

    reply = sections.get("REPLY", "").strip()

    corrections: list[str] = []
    body = sections.get("CORRECTIONS", "")
    if body and "NONE" not in body.upper():
        for line in body.splitlines():
            line = line.strip().lstrip("-*\u2022").strip()
            if line:
                corrections.append(line)

    vocab: list[dict] = []
    body = sections.get("VOCAB", "")
    if body and "NONE" not in body.upper():
        for chunk in re.split(r"[;\n]", body):
            chunk = chunk.strip().lstrip("-*\u2022").strip()
            if not chunk:
                continue
            if "=" in chunk:
                term, gloss = chunk.split("=", 1)
            elif "->" in chunk:
                term, gloss = chunk.split("->", 1)
            else:
                continue
            term, gloss = term.strip(), gloss.strip()
            if term and gloss:
                vocab.append({"term": term, "translation": gloss})

    return reply, corrections, vocab


def corrections_to_cards(corrections: list[str]) -> list[dict]:
    """Turn 'wrong -> right' corrections into review cards.

    A learner's own mistakes are the most valuable things to practise, so we make
    them into flashcards too -- not just the new vocabulary. Small models phrase
    these loosely, so we only take the ones with a clear 'x -> y' shape.
    """
    cards: list[dict] = []
    for c in corrections:
        if "->" not in c:
            continue
        wrong, right = c.split("->", 1)
        wrong = _tidy(wrong)
        right = _tidy(right)
        # keep the "why" if the model added one, e.g. "(use estar for states)"
        if wrong and right:
            cards.append({"term": wrong, "translation": right})
    return cards


def _tidy(fragment: str) -> str:
    """Trim bullets/quotes so a loosely formatted correction reads cleanly."""
    fragment = fragment.strip().lstrip("-*\u2022").strip()
    # drop stray quote marks that wrap a phrase, e.g. 'estoy cansado' (use estar...)
    fragment = re.sub(r"(^|(?<=\s))'|'(?=\s|$)", "", fragment)
    return fragment.strip()


def _normalize(messages: list[dict]) -> list[dict]:
    """Coerce a message list into the strict user-first alternation many chat
    templates require (Gemma's, for one) -- it otherwise rejects the request with
    'Conversation roles must alternate user/assistant/...'.

    We merge consecutive same-role turns and drop any leading assistant turns.
    This matters here because the tutor's opening line (from /api/drill) is stored
    as an assistant message, so a learner's first real turn would arrive as
    [assistant, user, ...] and 400 out of the local server.
    """
    cleaned: list[dict] = []
    for m in messages:
        role = m.get("role")
        content = str(m.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if cleaned and cleaned[-1]["role"] == role:
            cleaned[-1]["content"] += "\n" + content
        else:
            cleaned.append({"role": role, "content": content})
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    return cleaned


async def _detect(client: httpx.AsyncClient) -> tuple[str, str]:
    """Find a reachable server and a loaded model. Cached after success."""
    global _detected
    if _detected is not None:
        return _detected

    s = settings()
    bases = [s.llm_base_url] if s.llm_base_url else list(_CANDIDATES)
    headers = {"Authorization": f"Bearer {s.llm_api_key}"} if s.llm_api_key else None

    for base in bases:
        base = base.rstrip("/")
        try:
            resp = await client.get(f"{base}/models", timeout=3.0, headers=headers)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            model = s.llm_model or (data[0]["id"] if data else "")
            if model:
                _detected = (base, model)
                return _detected
        except Exception:
            continue

    raise LLMUnavailable(
        "No local model server found. Start LM Studio (Developer > Start Server) "
        "or `ollama serve`, load an open-weight model such as google/gemma-3-4b, "
        "then set LLM_BASE_URL / LLM_MODEL in .env if auto-detect fails."
    )


async def complete(system: str, messages: list[dict], *, temperature: float | None = None) -> TutorTurn:
    """Run one chat completion against the local model and parse the tutor format."""
    s = settings()
    convo = _normalize(messages) or messages
    payload_messages = [{"role": "system", "content": system}, *convo]

    headers = {"Authorization": f"Bearer {s.llm_api_key}"} if s.llm_api_key else None
    async with httpx.AsyncClient(timeout=s.llm_timeout) as client:
        base, model = await _detect(client)
        body = {
            "model": model,
            "messages": payload_messages,
            "temperature": s.llm_temperature if temperature is None else temperature,
            # Cap the reply so a small local model stays snappy instead of rambling.
            "max_tokens": s.llm_max_tokens,
            "stream": False,
        }
        started = time.perf_counter()
        resp = await client.post(f"{base}/chat/completions", json=body, headers=headers)
        resp.raise_for_status()
        latency_ms = int((time.perf_counter() - started) * 1000)
        data = resp.json()

    raw = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "")
    tokens = int((data.get("usage") or {}).get("total_tokens", 0) or 0)
    reply, corrections, vocab = _parse(raw)
    return TutorTurn(reply, corrections, vocab, raw, latency_ms, tokens)


async def health() -> dict:
    """Report which local model is in use, without raising. Used by /api/health."""
    s = settings()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            base, model = await _detect(client)
        return {"ok": True, "base_url": base, "model": model}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "configured_base": s.llm_base_url}
