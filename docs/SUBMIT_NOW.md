# SUBMIT NOW — 30-minute runbook (Oct 5)

**Deadline: 12:29 PM IST (6:59 AM UTC).** Everything in the repo is ready; the four
steps below need *your* logins (Render, Google Flow/YouTube, DEV) — they cannot be
automated from the repo.

---

## Step 1 — Deploy on Render (≈10 min) — *start now*

1. Go to <https://dashboard.render.com> → **New +** → **Blueprint**.
2. Connect the repo **`surajns0033-collab/linguapal`** and pick branch **`main`**.
3. Render reads [`../render.yaml`](../render.yaml) and prompts for the one secret:
   - **`LLM_API_KEY`** → paste your Google AI Studio key.
   - Everything else is pre-set:
     - `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`
     - `LLM_MODEL=gemma-4-26b-a4b-it`
     - `LLM_MAX_TOKENS=2048`
     - `DATA_DIR=/tmp/linguapal`, plan **free**
4. Click **Create** / **Apply**. Wait for the build (Docker, several minutes).

**Verify when live:**
- Open `https://<your-app>.onrender.com/api/health` → expect `{"ok": true, ...}` with `"model": "gemma-4-26b-a4b-it"`.
- Open the app URL, run setup → one chat turn → confirm the reply has **no `<thought>`** text.

**Then:** copy the app URL and paste it into [`../SUBMISSION.md`](../SUBMISSION.md)
where it says `Deployed app: **`[Render URL here]`**`.

> Free-tier note: the service sleeps after ~15 min idle, so the **first** request is
> slow. Hit `/api/health` once before recording the demo.

---

## Step 2 — Video (≈15 min) — Google Flow + screen recording

Full scene list: [`demo.svg`](demo.svg). Flow prompts + style lock:
[`FLOW_VIDEO_PROMPTS.md`](FLOW_VIDEO_PROMPTS.md).

Fast path:
1. Screen-record the live app in one take (phone is fine): setup → drill → a
   correction → flashcards → review → progress. ~60–90s.
2. *(Optional polish)* Generate the 6s **opening bumper** and 6s **closing card** in
   Google Flow using the prompts in `FLOW_VIDEO_PROMPTS.md`, then stitch in CapCut /
   Clipchamp (both free).
3. Export 1080p, upload **unlisted** to YouTube, copy the link.
4. Paste the link into [`../SUBMISSION.md`](../SUBMISSION.md) at `[video demo link here]`.

---

## Step 3 — Fill SUBMISSION.md (≈5 min)

Replace the three placeholders:
- `[video demo link here]` (Demo section)
- `[Render URL here]` (Demo section)
- `[her reaction here]` (What Maya Said) — ask her for one honest line; if you can't,
  write what changed for her in your words.

Optional: `[DevRelay session link here]` if you saved the agent session.

---

## Step 4 — Publish the DEV post (≈10 min) — *before 12:29 PM IST*

1. Open the DEV editor → **Write a post**.
2. Paste the whole of [`../SUBMISSION.md`](../SUBMISSION.md) (front-matter included, or
   set the fields via the UI: tags `devchallenge, weekendchallenge, hf26challenge`).
3. Flip `published: false` → `published: true` if you paste the front-matter.
4. **Publish**, then confirm it appears under
   <https://dev.to/challenges/hacktoberfest-weekend-2026-10-01>.

---

## After submission

Rotate/delete the Gemini API key at <https://aistudio.google.com/apikey> (the key was
shared in chat, so treat it as exposed).

---

## If Render stalls (fallback)

A repo + a local screen-recording demo is a valid submission. If the live URL isn't
ready, publish the post anyway and note "live URL coming shortly", then edit the post
once Render is up. **Priority: publish before the deadline.**
