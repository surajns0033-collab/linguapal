"""Offline smoke test: exercises the app without needing a model server.

Stubs the LLM layer, then drives setup, chat, card creation, and review grading
through the FastAPI TestClient. Run: python smoke_test.py
"""
import os
import tempfile

# Isolate the test database and avoid any network model calls.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="linguapal-test-")

from fastapi.testclient import TestClient  # noqa: E402

from app import llm, store  # noqa: E402
from app.llm import TutorTurn  # noqa: E402
from app.main import app  # noqa: E402


async def _fake_complete(system, messages, temperature=None):
    raw = (
        "REPLY: ¡Hola! ¿Cómo estás hoy? (Hi! How are you today?)\n"
        "CORRECTIONS: - 'yo soy cansado' -> 'estoy cansado' (use estar for states)\n"
        "VOCAB: cansado = tired; la mañana = the morning"
    )
    return TutorTurn("¡Hola! ¿Cómo estás hoy?", ["'yo soy cansado' -> 'estoy cansado'"],
                     [{"term": "cansado", "translation": "tired"},
                      {"term": "la mañana", "translation": "the morning"}],
                     raw, latency_ms=12, tokens=42)


async def _fake_health():
    return {"ok": True, "base_url": "http://localhost:1234/v1", "model": "test-model"}


def main() -> None:
    llm.complete = _fake_complete
    llm.health = _fake_health

    client = TestClient(app)

    assert client.get("/api/health").json()["model"]["ok"] is True
    assert client.get("/api/learner").json()["configured"] is False

    setup = client.post("/api/setup", json={"name": "Priya", "language": "Spanish", "level": "beginner"})
    assert setup.status_code == 200, setup.text
    assert setup.json()["learner"]["name"] == "Priya"

    chat = client.post("/api/chat", json={"message": "hola, yo soy cansado hoy"}).json()
    assert "Hola" in chat["reply"], chat
    assert chat["corrections"], "expected at least one correction"
    assert len(chat["vocab"]) == 2, chat["vocab"]
    assert chat["stats"]["cards"] == 2, chat["stats"]

    cards = client.get("/api/review").json()["cards"]
    assert len(cards) == 2, cards
    graded = client.post("/api/review", json={"card_id": cards[0]["id"], "quality": 3}).json()
    assert graded["ok"] and graded["card"]["reps"] == 1, graded

    stats = client.get("/api/stats").json()["stats"]
    assert stats["cards"] == 2 and stats["turns"] == 1, stats

    print("SMOKE TEST PASSED")
    print("  learner:", setup.json()["learner"])
    print("  chat:", {"reply": chat["reply"], "corrections": chat["corrections"], "vocab": chat["vocab"]})
    print("  stats:", stats)


if __name__ == "__main__":
    main()
