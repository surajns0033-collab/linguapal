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


def _parse(raw: str) -> tuple[str, list[str], list[dict]]:
    """Parse the strict REPLY/CORRECTIONS/VOCAB format the prompt asks for."""
    reply, corrections, vocab = raw.strip(), [], []

    m = re.search(r"REPLY:\s*(.*?)(?=\n\s*(?:CORRECTIONS|VOCAB):|\Z)", raw, re.S | re.I)
    if m:
        reply = m.group(1).strip()

    m = re.search(r"CORRECTIONS:\s*(.*?)(?=\n\s*(?:REPLY|VOCAB):|\Z)", raw, re.S | re.I)
    if m and "NONE" not in m.group(1).upper():
        for line in m.group(1).splitlines():
            line = line.strip().lstrip("-*\u2022").strip()
            if line:
                corrections.append(line)

    m = re.search(r"VOCAB:\s*(.*?)(?=\n\s*(?:REPLY|CORRECTIONS):|\Z)", raw, re.S | re.I)
    if m and "NONE" not in m.group(1).upper():
        for chunk in re.split(r"[;\n]", m.group(1)):
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


async def _detect(client: httpx.AsyncClient) -> tuple[str, str]:
    """Find a reachable local server and a loaded model. Cached after success."""
    global _detected
    if _detected is not None:
        return _detected

    s = settings()
    bases = [s.llm_base_url] if s.llm_base_url else list(_CANDIDATES)

    for base in bases:
        base = base.rstrip("/")
        try:
            resp = await client.get(f"{base}/models", timeout=3.0)
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
    payload_messages = [{"role": "system", "content": system}, *messages]

    async with httpx.AsyncClient(timeout=s.llm_timeout) as client:
        base, model = await _detect(client)
        body = {
            "model": model,
            "messages": payload_messages,
            "temperature": s.llm_temperature if temperature is None else temperature,
            "stream": False,
        }
        started = time.perf_counter()
        resp = await client.post(f"{base}/chat/completions", json=body)
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
