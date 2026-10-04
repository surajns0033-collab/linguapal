---
title: "LinguaPal: a tiny offline language tutor I built for one friend"
published: false
tags: devchallenge, weekendchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

## What I Built

My friend Maya is learning Spanish. She's not afraid of grammar drills — she's
afraid of *speaking*. Every app she tried sent her halting, half-wrong sentences
to some company's server, and every time she got something wrong she felt like
she was being graded. She told me: *"I want to practice without feeling watched."*

So I built **LinguaPal** for her. It's a tiny practice partner that runs on her
own laptop. It:

- holds a conversation in Spanish at her level, and never gets tired or impatient;
- corrects her gently, right inside the reply — *"you wrote `yo soy cansado`; for a
  state like this, `estoy cansado`"* — with a one-line reason, never a red mark;
- turns every new word it introduces into a flashcard automatically;
- brings those words back later with a small spaced-repetition scheduler, so they
  actually stick;
- remembers the words she keeps forgetting and quietly weaves them into the next
  conversation;
- reacts as she practises: a little companion **orb** shows the tutor's mood
  (thinking, happy, gently-correcting) with a sprinkling of emoji, so it feels like
  a pal rather than a grader — a small thing that turned out to matter most.

The whole thing is one FastAPI app and a page of plain JavaScript. No account, no
signup, no analytics.

## Demo

<!-- Add a short screen recording (a 60-90s clip is plenty): setup → a few turns
     with corrections → the review queue → progress stats updating. -->
`[video demo link here]`

Deployed app: **`[Render URL here]`** — live on **Render**. You don't need a local
GPU to try it: the hosted app points `LLM_BASE_URL` at an OpenAI-compatible
**open-weight** endpoint (any served Gemma/Llama/Qwen), and the same app runs fully
offline on Maya's laptop with LM Studio or Ollama. One variable, two deployments.

## Code

[github.com/surajns0033-collab/linguapal](https://github.com/surajns0033-collab/linguapal) — MIT licensed.

The interesting bits:
- `app/llm.py` — talks to a **local, OpenAI-compatible open-weight server** (LM Studio or Ollama).
- `app/prompts.py` — a strict `REPLY / CORRECTIONS / VOCAB` contract so one local call yields the reply *and* the feedback.
- `app/srs.py` — a dependency-free small spaced-repetition scheduler.
- `app/store.py` — everything (learner, history, cards) in a single local SQLite file.

## How I Built It

The core of LinguaPal is **an open-weight model** — during the challenge the tutor
ran on **Gemma 3n E2B** (2.79 GB, quantised), loaded in LM Studio on my own laptop.
`app/llm.py` speaks the OpenAI-compatible chat API, so the model is a swappable
part of the stack — not a hard dependency on anyone's cloud. Pinning it to Gemma,
or moving it from a laptop to a hosted endpoint, is one line in `.env`.

That last point matters for the deployed demo: an open-weight model is normally
served the same way everywhere, so the *identical* app talks to a laptop LM Studio
server **or** to a remote OpenAI-compatible open-weight endpoint (`LLM_BASE_URL` +
optional `LLM_API_KEY`). The hosted link and the offline laptop build are the same
code — only the endpoint differs. There is no closed API anywhere in the loop.

The one design constraint that shaped everything: **a small local model is slower
and less chatty than a frontier API.** So I stopped treating the model as an
oracle and treated it as a component. The prompt asks for a strict three-part
reply — the conversation, a list of corrections, and any new vocabulary — and
`app/llm.py` parses that into structured data. One local inference gives me the
reply *and* the feedback *and* the flashcards. The spaced-repetition scheduler
lives in plain Python (`app/srs.py`), not in the model, so the learner's progress
is deterministic and instant. The result feels responsive even on a 4B model
running on a laptop.

Open-source AI is the point, not a garnish: the model *is* the tutor. Everything
around it just makes a small local model feel like a patient friend.

## Why Does Open Innovation Matter?

For this project, running on an open-weight model locally isn't a nice-to-have — it
is the feature. Maya's exact fear was being watched while she practices, and the
open approach removes that fear at the root:

- **Her practice never leaves her laptop.** Not "we don't log it" — it simply
  *can't* leave, because there's no remote API in the loop. That's the difference
  between a privacy *policy* and a privacy *guarantee*.
- **It works with no internet.** She practices Spanish on the metro, offline.
- **It costs nothing to run**, so she never feels she's "using up" someone's tokens
  and can't afford to make a hundred mistakes. For a shy learner, that changes
  everything.
- **The model is swappable — and so is *where* it runs.** Gemma today, Llama or
  Qwen tomorrow; on her laptop tonight, on a small hosted open-weight endpoint when
  she wants a public link. One env var, same app. A closed endpoint would lock her
  progress behind one vendor's pricing and one vendor's model.
- **No GPU required to try it.** The deployed demo uses an open-weight endpoint, so
  anyone can open a link and practise — then run the exact same code fully offline.
  Open weights make the offline build and the hosted build the *same* program.
- **She can own it.** It's MIT-licensed. If she wants to change the tone, the
  corrections, the scheduler, she just edits it. A gift you can open the hood on.

A closed API would have made this an app about a subscription. Open weights made it
a gift.

**Deployment (Best Use of Render):** the FastAPI app and front end are deployed on
**Render**, so the app is always reachable, while the open-weight model runs on the
learner's own machine (or any open-weight server you point `LLM_BASE_URL` at). That
split is deliberate: the always-on, low-sensitivity part lives in the cloud; the
private part — her conversations — stays local.

## My Agent Session

<!-- Optional but judges like it: save the session with DevRelay and embed/link it. -->
`[DevRelay session link here]`

## Prize Categories

- **Best Use of Gemma** — Gemma is the tutor's core. The challenge allows three ways
  to use it, and LinguaPal is built so the first two need *no code change*:
  **(a) run it locally** — the demo ran on **Gemma 3n E2B** in LM Studio on my laptop;
  **(b) serve it through a provider** — point `LLM_BASE_URL` at any OpenAI-compatible
  open-weight endpoint (e.g. a served Gemma on Google Cloud or another provider) and the
  same app runs hosted. **(c) fine-tune it** — because the model sits behind the single
  `app/llm.py` seam, a Gemma fine-tuned to Maya's level drops in as just another
  `LLM_MODEL`, with nothing else in the app touched.
- **Best Use of Render** — the app/front end is deployed on Render.

## What Maya Said

<!-- The prompt says bonus points for handing it over — so hand it over and quote her. -->
`"[her reaction here]"`

---

*Built solo during the Hacktoberfest Weekend Challenge window, Oct 2–5, 2026.
Open-source AI at the core; MIT licensed; no data leaves the learner's machine.*
