"""LinguaPal HTTP API and static front end.

A small, friendly tutor for one real person, powered by a local open-weight
model. The whole study loop -- conversation, gentle corrections, a spaced
repetition review queue, and a progress view -- lives here.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import llm, store
from .config import settings
from .prompts import drill_prompt, tutor_system_prompt

app = FastAPI(title="LinguaPal", version="1.0.0")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

store.init_db()


# --- models -----------------------------------------------------------------
class Setup(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    language: str = Field(..., min_length=1, max_length=40)
    level: str = Field("beginner", pattern="^(beginner|intermediate|advanced)$")


class ChatIn(BaseModel):
    message: str = Field("", max_length=4000)


class GradeIn(BaseModel):
    card_id: int
    quality: int = Field(..., ge=0, le=3)


# --- helpers ----------------------------------------------------------------
def _learner() -> dict:
    with store._conn() as conn:  # small project: reuse the store connection
        row = conn.execute("SELECT * FROM learner ORDER BY id LIMIT 1").fetchone()
    if not row:
        raise HTTPException(409, "No learner configured yet.")
    return dict(row)


def _public_learner(row: dict) -> dict:
    return {
        "name": row["name"],
        "language": row["language"],
        "level": row["level"],
        "stats": store.stats(row["id"]),
    }


# --- API --------------------------------------------------------------------
@app.get("/api/health")
async def health() -> dict:
    return {"app": "ok", "model": await llm.health()}


@app.get("/api/learner")
async def get_learner() -> dict:
    with store._conn() as conn:
        row = conn.execute("SELECT * FROM learner ORDER BY id LIMIT 1").fetchone()
    return {"configured": bool(row), "learner": _public_learner(dict(row)) if row else None}


@app.post("/api/setup")
async def setup(payload: Setup) -> dict:
    with store._conn() as conn:
        row = conn.execute("SELECT id FROM learner ORDER BY id LIMIT 1").fetchone()
    if row:
        store.update_learner(row["id"], name=payload.name, language=payload.language, level=payload.level)
    else:
        store.get_or_create_learner(payload.name, payload.language, payload.level)
    return {"ok": True, "learner": _public_learner(_learner())}


@app.post("/api/chat")
async def chat(payload: ChatIn) -> dict:
    learner = _learner()
    user_text = payload.message.strip()
    if user_text:
        store.add_message(learner["id"], "user", user_text)

    # A short window keeps the prompt small (faster on a laptop) while still
    # giving the tutor enough context to stay on topic.
    history = store.recent_messages(learner["id"], limit=6)
    system = tutor_system_prompt(
        learner["language"], learner["level"], learner["name"], store.weak_items(learner["id"])
    )

    try:
        turn = await llm.complete(system, history)
    except llm.LLMUnavailable as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:  # network/parse issues from the local server
        raise HTTPException(502, f"Local model error: {exc}")

    store.add_message(learner["id"], "assistant", turn.text,
                      corrections=turn.corrections, latency_ms=turn.latency_ms, tokens=turn.tokens)

    # New vocabulary and the learner's own mistakes both become review cards,
    # so the things they got wrong are exactly what comes back to practise.
    new_cards = turn.vocab + llm.corrections_to_cards(turn.corrections)
    for item in new_cards:
        store.upsert_card(learner["id"], item["term"], item["translation"])

    return {
        "reply": turn.text,
        "corrections": turn.corrections,
        "vocab": turn.vocab,
        "latency_ms": turn.latency_ms,
        "tokens": turn.tokens,
        "stats": store.stats(learner["id"]),
    }


@app.get("/api/drill")
async def drill(topic: str = "everyday life") -> dict:
    """Have the tutor open a fresh practice conversation about a topic."""
    learner = _learner()
    system = drill_prompt(learner["language"], learner["level"], topic)
    try:
        turn = await llm.complete(system, [{"role": "user", "content": f"Let's practice: {topic}"}])
    except llm.LLMUnavailable as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"Local model error: {exc}")

    store.add_message(learner["id"], "assistant", turn.text, corrections=turn.corrections)
    new_cards = turn.vocab + llm.corrections_to_cards(turn.corrections)
    for item in new_cards:
        store.upsert_card(learner["id"], item["term"], item["translation"])
    return {"reply": turn.text, "corrections": turn.corrections, "vocab": turn.vocab}


@app.get("/api/review")
async def review_queue() -> dict:
    learner = _learner()
    return {"cards": store.due_cards(learner["id"]), "stats": store.stats(learner["id"])}


@app.post("/api/review")
async def review_grade(payload: GradeIn) -> dict:
    result = store.grade_card(payload.card_id, payload.quality)
    if not result:
        raise HTTPException(404, "Card not found.")
    return {"ok": True, "card": result}


@app.get("/api/stats")
async def get_stats() -> dict:
    return {"stats": store.stats(_learner()["id"])}


@app.post("/api/reset")
async def reset() -> dict:
    """Clear the local practice history so someone new can start (used for a fresh demo)."""
    store.reset()
    return {"ok": True}


# --- static front end -------------------------------------------------------
@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
