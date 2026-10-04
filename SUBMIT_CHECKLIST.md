# Final submission checklist — Hacktoberfest Weekend Challenge

Deadline: **October 5, 2026, 6:59 AM UTC** = **12:29 PM IST**.

## Rules compliance (mapped to this project)

- [x] **Open-source AI at the core** — a local open-weight model is the tutor itself
      (`app/llm.py` targets an OpenAI-compatible open-weight server; LM Studio/Ollama).
- [x] **New project, built inside the window (Oct 2–5)** — first commit made in-window.
- [x] **No PRs to existing projects** — this is a standalone new app.
- [x] **Open-source code credited & significant** — all code here is original; only
      standard open-source libraries (FastAPI, httpx) are used.
- [x] **English write-up** — [`SUBMISSION.md`](SUBMISSION.md) is in English.
- [x] **Required tags** — `devchallenge`, `weekendchallenge`, `hf26challenge` in the front matter.
- [x] **Prize Categories section** — lists Gemma + Render.
- [x] **Privacy / data handling** — everything stays in a local SQLite file; nothing is uploaded.
- [x] **MIT licensed** — [`LICENSE`](LICENSE).

## Judging criteria — how this submission scores

- **Writing Quality (heaviest)** → the draft tells one person's story, is structured
  around the required sections, and keeps each "why open" claim concrete.
- **Relevance to Prompt & Theme** → literally "build for a friend": named friend,
  real fear (being watched), a small tool that matters to her.
- **Creativity** → corrections + flashcards + spaced repetition extracted from a
  single small-model call; weak-spot memory fed back into the prompt.
- **Technical Execution** → clean FastAPI + SQLite + vanilla JS; smoke test passes;
  swappable model layer; Docker + Render deploy included.
- **Use of Partner Technology** → Gemma (open-weight core) and Render (deployment).

## Manual steps still required (you)

1. **Start the model.** In LM Studio: load an open-weight model (developed and demoed
   on `google/gemma-3n-e2b`; `google/gemma-3-4b` also works) and Developer →
   **Start Server** (port 1234). Or `ollama serve` + `ollama pull gemma3:4b`.
2. **Run it:** `.venv\Scripts\activate` → `pip install -r requirements.txt` →
   `copy .env.example .env` → `uvicorn app.main:app --reload --port 8000`.
3. **Try it with the real friend** and capture her reaction.
4. **Record a 60–90s demo video** (setup → a few turns with corrections → review queue → stats).
5. **Push to GitHub** (a fresh public repo — all commits inside the window).
6. **Deploy to Render** using [`render.yaml`](render.yaml); set `LLM_BASE_URL`,
   `LLM_MODEL`, and (if the endpoint needs one) `LLM_API_KEY`. Point it at any
   OpenAI-compatible **open-weight** endpoint so the hosted app works without a
   local GPU. Save the URL.
7. **Fill the placeholders** in [`SUBMISSION.md`](SUBMISSION.md): demo video link,
   Render URL, GitHub repo link, DevRelay session link, and "What Maya Said".
8. **Publish on DEV** using the challenge's submission template, set the post to
   `published: true`, and confirm the three tags are present.

## Optional upgrades (only if time remains)

- **Tinker** — fine-tune a tiny model on the friend's common mistakes and show the
  improvement (adds *Best Use of Tinker*, and a strong before/after story).

## The one-line pitch

> LinguaPal is a small language tutor that runs on a friend's own laptop, so she can
> practice out loud, make a hundred mistakes, and never feel watched.
