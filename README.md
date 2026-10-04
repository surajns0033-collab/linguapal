# LinguaPal — a little language tutor, built for one friend

LinguaPal is a small, friendly practice partner for **one real person**: my friend
who is learning a new language and gets shy practising out loud. It runs on a
**local open-weight model**, keeps every bit of her practice on her own machine,
and quietly remembers the words she keeps forgetting.

Built for the **Hacktoberfest Weekend Challenge: Build for a Friend** (Oct 2–5, 2026).

## Who it's for

Someone learning a language who wants a patient partner that never gets tired and
never sends their mistakes to a company's server. You point it at their level, and
it just chats — gently correcting, feeding back the words they lapse on, and
tracking what's actually sticking.

## What it does

- **Conversation practice** in the target language, tuned to beginner/intermediate/advanced.
- **Gentle corrections** parsed out of the model's reply (never mocked, always explained).
- **Automatic vocabulary cards** — every new word the tutor introduces becomes a review card.
- **Spaced repetition review** (a small SM-2 scheduler) so the words come back at the right time.
- **Progress that means something** — retention %, cards due now, matured cards, turns practised.
- **A durable memory of weak spots** — terms the learner keeps lapsing on are woven back into future prompts.
- **A friendly companion mood** — the orb, colours, and emoji reactions make it feel like a pal, not a grader.

## Why open innovation matters here

LinguaPal's core is an **open-weight model** served locally. That is not a detail —
it is the whole point, and it is what a closed API could not give us:

- **Private by default.** A beginner's halting sentences are exactly the kind of thing
  people don't want on someone else's server. Everything lives in one local SQLite file.
- **Runs on a laptop, even offline.** Language practice on a train or a flight still works.
- **Zero marginal cost.** Practice as much as you like; there is no per-token bill, which
  matters for a friend who would feel guilty "using up" an API.
- **Swappable models — and a swappable place to run them.** The same app drives Gemma,
  Llama, or Qwen — LM Studio or Ollama locally, or any OpenAI-compatible open-weight
  endpoint when hosted (`LLM_BASE_URL` + optional `LLM_API_KEY`). One env var moves it
  from a laptop to the cloud; no closed API is ever in the loop.
- **Yours to change.** The prompt, the scheduler, the UI — all forks of a friend's gift,
  not a locked product.

## Architecture

```
Browser (static/, no framework)  ──►  FastAPI (app/main.py)
                                        ├─ llm.py     → OpenAI-compatible endpoint
                                        │              (LM Studio :1234, Ollama :11434,
                                        │               or a hosted open-weight server)
                                        ├─ prompts.py → tutor + drill prompts
                                        ├─ store.py   → SQLite: learner, messages, cards
                                        └─ srs.py     → spaced-repetition scheduler
```

An OpenAI-compatible endpoint is used — a local one by default (LM Studio/Ollama),
or a remote open-weight endpoint when deployed. The open-weight model is a swappable
component, not a hard dependency on any vendor.

## Run it locally

1. **Start an open-weight model.** Either:
   - **LM Studio**: load a small model (developed and demoed on `google/gemma-3n-e2b`; `google/gemma-3-4b` or `llama-3.2-3b` also work), then Developer → **Start Server** (port 1234), or
   - **Ollama**: `ollama serve` and `ollama pull gemma3:4b`.
2. **Install and run:**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # Windows (macOS/Linux: source .venv/bin/activate)
   pip install -r requirements.txt
   copy .env.example .env        # then edit if needed
   uvicorn app.main:app --reload --port 8000
   ```

3. Open <http://localhost:8000>, tell it who you're helping, and start practising.

Auto-detection tries LM Studio, then Ollama. Override with `LLM_BASE_URL` / `LLM_MODEL`
in `.env` for any other OpenAI-compatible open-weight server.

## Hosted mode (Render — Best Use of Render)

Render hosts the **app/front end**; the open-weight model can run locally on the
learner's machine or on any open-weight server you point at:

- Set `LLM_BASE_URL` to that server's `/v1` URL, `LLM_MODEL` to its model id, and
  `LLM_API_KEY` if the endpoint requires one — so the hosted app works with no local GPU.
- Deploy the repo to Render as a **Web Service** (Dockerfile included, see `render.yaml`).
- Set `DATA_DIR` to a mounted disk if you want review history to persist.

This keeps the friend's data under their control while the app is always reachable.

## Partner categories entered

- **Best Use of Gemma** — Gemma is the tutor's core, run locally (LM Studio/Ollama) or
  served through any OpenAI-compatible provider: one env var swaps it, no code change.
- **Best Use of Render** — the app/front end is deployed on Render.

## Configuration

See [`.env.example`](.env.example). Nothing is required beyond a running local model.

## License

MIT — fork it, adapt it, give it to your own friend.
