"""Small offline SQLite store: learner profile, chat history, and review cards.

One local file means the learner's data never has to touch a server they don't
control -- a concrete win of building on open, local AI.
"""
from __future__ import annotations

import json
import sqlite3
import time

from .config import settings
from .srs import CardState, review

_SCHEMA = """
CREATE TABLE IF NOT EXISTS learner (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    language   TEXT NOT NULL,
    level      TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY,
    learner_id  INTEGER NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    corrections TEXT,
    latency_ms  INTEGER DEFAULT 0,
    tokens      INTEGER DEFAULT 0,
    created_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
    id         INTEGER PRIMARY KEY,
    learner_id INTEGER NOT NULL,
    front      TEXT NOT NULL,
    back       TEXT NOT NULL,
    ease       REAL DEFAULT 2.5,
    interval   REAL DEFAULT 0,
    reps       INTEGER DEFAULT 0,
    lapses     INTEGER DEFAULT 0,
    due_at     REAL NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE(learner_id, front)
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings().db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def init_db() -> None:
    with _conn():
        pass


def get_or_create_learner(name: str, language: str, level: str) -> dict:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM learner ORDER BY id LIMIT 1").fetchone()
        if row:
            return dict(row)
        cur = conn.execute(
            "INSERT INTO learner (name, language, level, created_at) VALUES (?,?,?,?)",
            (name, language, level, time.time()),
        )
        row = conn.execute("SELECT * FROM learner WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)


def update_learner(learner_id: int, *, name: str, language: str, level: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE learner SET name=?, language=?, level=? WHERE id=?",
            (name, language, level, learner_id),
        )


def add_message(learner_id: int, role: str, content: str, *,
                corrections: list[str] | None = None,
                latency_ms: int = 0, tokens: int = 0) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO messages (learner_id, role, content, corrections, latency_ms, tokens, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (learner_id, role, content, json.dumps(corrections or []), latency_ms, tokens, time.time()),
        )


def recent_messages(learner_id: int, limit: int = 12) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE learner_id=? ORDER BY id DESC LIMIT ?",
            (learner_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def upsert_card(learner_id: int, front: str, back: str) -> None:
    now = time.time()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO cards (learner_id, front, back, due_at, created_at)"
            " VALUES (?,?,?,?,?)"
            " ON CONFLICT(learner_id, front) DO UPDATE SET back=excluded.back",
            (learner_id, front.strip(), back.strip(), now, now),
        )


def due_cards(learner_id: int, limit: int = 10) -> list[dict]:
    now = time.time()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cards WHERE learner_id=? AND due_at<=? ORDER BY due_at LIMIT ?",
            (learner_id, now, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def grade_card(card_id: int, quality: int) -> dict:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if not row:
            return {}
        state = CardState(
            ease=row["ease"], interval=row["interval"], reps=row["reps"], lapses=row["lapses"]
        )
        state, due_at = review(state, quality)
        conn.execute(
            "UPDATE cards SET ease=?, interval=?, reps=?, lapses=?, due_at=? WHERE id=?",
            (state.ease, state.interval, state.reps, state.lapses, due_at, card_id),
        )
    return {"id": card_id, "due_at": due_at, "interval": state.interval, "reps": state.reps}


def weak_items(learner_id: int, limit: int = 8) -> list[str]:
    """Terms the learner has lapsed on most -- fed back into the tutor prompt."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT front FROM cards WHERE learner_id=? AND lapses>0 ORDER BY lapses DESC, due_at ASC LIMIT ?",
            (learner_id, limit),
        ).fetchall()
    return [r["front"] for r in rows]


def stats(learner_id: int) -> dict:
    now = time.time()
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM cards WHERE learner_id=?", (learner_id,)).fetchone()["c"]
        due = conn.execute("SELECT COUNT(*) c FROM cards WHERE learner_id=? AND due_at<=?", (learner_id, now)).fetchone()["c"]
        matured = conn.execute("SELECT COUNT(*) c FROM cards WHERE learner_id=? AND reps>=3", (learner_id,)).fetchone()["c"]
        turns = conn.execute("SELECT COUNT(*) c FROM messages WHERE learner_id=? AND role='user'", (learner_id,)).fetchone()["c"]
    retention = round(100 * (total - due) / total) if total else 0
    return {"cards": total, "due": due, "matured": matured, "turns": turns, "retention": retention}
