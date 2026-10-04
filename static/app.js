"use strict";

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
    const res = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...opts,
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
    return body;
}

function setModelBadge(health) {
    const el = $("modelBadge");
    const m = health.model || {};
    if (m.ok) {
        el.textContent = `model: ${m.model}`;
        el.className = "badge badge--ok";
    } else {
        el.textContent = "no model detected";
        el.className = "badge badge--bad";
        el.title = m.error || "";
    }
}

function renderStats(stats) {
    if (!stats) return;
    $("sRetention").textContent = `${stats.retention}%`;
    $("sDue").textContent = stats.due;
    $("sMatured").textContent = stats.matured;
    $("sTurns").textContent = stats.turns;
}

function escapeHtml(s) {
    const code = String.fromCharCode;
    const amp = code(38);
    const map = {
        [code(38)]: amp + "amp;",
        [code(60)]: amp + "lt;",
        [code(62)]: amp + "gt;",
        [code(34)]: amp + "quot;",
        [code(39)]: amp + "#39;",
    };
    return String(s).replace(/[&<>"']/g, (c) => map[c]);
}

// --- the companion orb: a small animated mood indicator, with emoji feedback.
function setOrb(state, face, text) {
    const orb = $("orb");
    if (!orb) return;
    orb.dataset.state = state;
    if (face) $("orbFace").textContent = face;
    if (text) $("orbStatus").textContent = text;
    if (state === "happy" || state === "oops") burst(face || "✨");
}

function burst(emoji) {
    const wrap = $("orbWrap");
    if (!wrap) return;
    for (let i = 0; i < 6; i++) {
        const span = document.createElement("span");
        span.className = "orbSpark";
        span.textContent = emoji;
        span.style.setProperty("--dx", (Math.random() * 2 - 1).toFixed(2));
        span.style.setProperty("--dy", (-0.4 - Math.random()).toFixed(2));
        wrap.appendChild(span);
        setTimeout(() => span.remove(), 950);
    }
}

function addBubble(role, text, corrections = [], vocab = []) {
    const wrap = document.createElement("div");
    wrap.className = `bubble ${role}`;
    wrap.textContent = text;

    if (corrections && corrections.length) {
        const c = document.createElement("div");
        c.className = "corr";
        c.innerHTML = "😅 <strong>A gentle fix</strong><br>" + corrections.map(escapeHtml).join("<br>");
        wrap.appendChild(c);
    }
    if (vocab && vocab.length) {
        const v = document.createElement("div");
        v.className = "vocab";
        v.innerHTML = "🌱 <strong>New words</strong>";
        const chips = document.createElement("div");
        chips.className = "chips";
        vocab.forEach((w) => {
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.textContent = `${w.term} = ${w.translation}`;
            chips.appendChild(chip);
        });
        v.appendChild(chips);
        wrap.appendChild(v);
    }
    $("messages").appendChild(wrap);
    $("messages").scrollTop = $("messages").scrollHeight;
}

async function loadReview() {
    const { cards, stats } = await api("/api/review");
    renderStats(stats);
    const box = $("review");
    box.innerHTML = "";
    if (!cards.length) {
        box.innerHTML = '<p class="empty">Nothing due right now. Keep chatting — new words become cards automatically.</p>';
        return;
    }
    cards.forEach((card) => box.appendChild(reviewCard(card)));
}

function reviewCard(card) {
    const el = document.createElement("div");
    el.className = "reviewCard";
    el.innerHTML = `<div class="front">${escapeHtml(card.front)}</div>
    <div class="back" hidden>${escapeHtml(card.back)}</div>
    <div class="reveal"><button>Show answer</button></div>`;
    const back = el.querySelector(".back");
    const reveal = el.querySelector(".reveal");
    reveal.querySelector("button").onclick = () => {
        back.hidden = false;
        reveal.innerHTML = "";
        const row = document.createElement("div");
        row.className = "gradeRow";
        [["Again", 0], ["Hard", 1], ["Good", 2], ["Easy", 3]].forEach(([label, q]) => {
            const b = document.createElement("button");
            b.textContent = label;
            b.onclick = async () => {
                await api("/api/review", { method: "POST", body: JSON.stringify({ card_id: card.id, quality: q }) });
                loadReview();
            };
            row.appendChild(b);
        });
        reveal.appendChild(row);
    };
    return el;
}

// --- one tutor turn, with a watchdog so the orb can never hang on "thinking".
async function runTurn(statusText, doFetch) {
    $("btnSend").disabled = true;
    setOrb("thinking", "🤔", statusText);
    const watchdog = setTimeout(
        () => setOrb("error", "😵", "Taking too long — is the model still running?"),
        90000
    );
    try {
        const data = await doFetch();
        addBubble("tutor", data.reply, data.corrections, data.vocab);
        if (data.stats) renderStats(data.stats);
        loadReview();
        const clean = !data.corrections || !data.corrections.length;
        setOrb(clean ? "happy" : "oops", clean ? "😄" : "😅",
            clean ? "Nice — no fixes needed." : "One small fix, then onward.");
        setTimeout(() => setOrb("idle", "🙂", "Your turn — type your reply."), 1400);
    } catch (e) {
        setOrb("error", "😵", e.message);
        addBubble("tutor", "⚠️ " + e.message);
    } finally {
        clearTimeout(watchdog);
        $("btnSend").disabled = false;
        $("inMsg").focus();
    }
}

async function sendMessage(text) {
    text = (text || "").trim();
    if (!text) return;
    addBubble("user", text);
    $("inMsg").value = "";
    await runTurn("Thinking…", () =>
        api("/api/chat", { method: "POST", body: JSON.stringify({ message: text }) }));
}

async function newPrompt() {
    const topic = $("inTopic").value.trim() || "everyday life";
    $("btnDrill").disabled = true;
    try {
        await runTurn("Setting up a new topic…", () =>
            api(`/api/drill?topic=${encodeURIComponent(topic)}`));
    } finally {
        $("btnDrill").disabled = false;
    }
}

function showApp(learner) {
    $("setupCard").hidden = true;
    $("chatCard").hidden = false;
    $("btnReset").hidden = false;
    $("chatTitle").textContent = `Practising ${learner.language} with ${learner.name}`;
    setOrb("idle", "🙂", `Ready when you are — let's practise ${learner.language}.`);
    renderStats(learner.stats);
}

async function boot() {
    const health = await api("/api/health").catch(() => ({ model: { ok: false } }));
    setModelBadge(health);

    const state = await api("/api/learner");
    if (state.configured) {
        showApp(state.learner);
        loadReview();
    } else {
        $("setupCard").hidden = false;
    }
}

// --- wiring ---
$("btnSetup").onclick = async () => {
    const name = $("inName").value.trim();
    const language = $("inLang").value.trim();
    if (!name || !language) return;
    const data = await api("/api/setup", {
        method: "POST",
        body: JSON.stringify({ name, language, level: $("inLevel").value }),
    });
    showApp(data.learner);
    newPrompt();
};

async function resetLearner() {
    if (!confirm("Start over? This clears the local practice history on this machine.")) return;
    await api("/api/reset", { method: "POST" });
    $("messages").innerHTML = "";
    $("review").innerHTML = "";
    $("chatCard").hidden = true;
    $("btnReset").hidden = true;
    $("setupCard").hidden = false;
    renderStats({ retention: 0, due: 0, matured: 0, turns: 0 });
}

$("chatForm").onsubmit = (e) => { e.preventDefault(); sendMessage($("inMsg").value); };
$("btnDrill").onclick = newPrompt;
$("btnReload").onclick = loadReview;
$("btnReset").onclick = resetLearner;
$("inMsg").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage($("inMsg").value); }
});

boot();
