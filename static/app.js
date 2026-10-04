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
        el.textContent = `local model: ${m.model}`;
        el.className = "badge badge--ok";
    } else {
        el.textContent = "no local model detected";
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

function addBubble(role, text, corrections = [], vocab = []) {
    const wrap = document.createElement("div");
    wrap.className = `bubble ${role}`;
    wrap.textContent = text;

    if (corrections && corrections.length) {
        const c = document.createElement("div");
        c.className = "corr";
        c.innerHTML = "<strong>A gentle fix</strong><br>" + corrections.map(escapeHtml).join("<br>");
        wrap.appendChild(c);
    }
    if (vocab && vocab.length) {
        const v = document.createElement("div");
        v.className = "vocab";
        v.innerHTML = "<strong>New words</strong>";
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

function escapeHtml(s) {
    // Build entities from char codes so the source never contains raw entities.
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

async function sendMessage(text) {
    if (!text.trim()) return;
    addBubble("user", text);
    $("inMsg").value = "";
    $("btnSend").disabled = true;
    try {
        const data = await api("/api/chat", { method: "POST", body: JSON.stringify({ message: text }) });
        addBubble("tutor", data.reply, data.corrections, data.vocab);
        renderStats(data.stats);
        loadReview();
    } catch (e) {
        addBubble("tutor", "⚠️ " + e.message);
    } finally {
        $("btnSend").disabled = false;
        $("inMsg").focus();
    }
}

async function newPrompt() {
    const topic = $("inTopic").value.trim() || "everyday life";
    $("btnDrill").disabled = true;
    try {
        const data = await api(`/api/drill?topic=${encodeURIComponent(topic)}`);
        addBubble("tutor", data.reply, data.corrections, data.vocab);
    } catch (e) {
        addBubble("tutor", "⚠️ " + e.message);
    } finally {
        $("btnDrill").disabled = false;
    }
}

function showApp(learner) {
    $("setupCard").hidden = true;
    $("chatCard").hidden = false;
    $("chatTitle").textContent = `Practising ${learner.language} with ${learner.name}`;
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

$("chatForm").onsubmit = (e) => { e.preventDefault(); sendMessage($("inMsg").value); };
$("btnDrill").onclick = newPrompt;
$("btnReload").onclick = loadReview;
$("inMsg").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage($("inMsg").value); }
});

boot();
