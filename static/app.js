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

// --- voice: map a language name to a BCP-47 tag for speech synthesis/recognition.
const LANG_TAGS = {
    spanish: "es-ES", french: "fr-FR", german: "de-DE", italian: "it-IT",
    portuguese: "pt-BR", japanese: "ja-JP", korean: "ko-KR", chinese: "zh-CN",
    mandarin: "zh-CN", hindi: "hi-IN", arabic: "ar-SA", russian: "ru-RU",
    dutch: "nl-NL", turkish: "tr-TR", polish: "pl-PL", swedish: "sv-SE",
    english: "en-US",
};
let targetTag = "es-US";
let voiceOn = true;

function tagFor(language) {
    const key = String(language || "").toLowerCase().trim();
    for (const k in LANG_TAGS) if (key.includes(k)) return LANG_TAGS[k];
    return "en-US";
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

// --- speech out: read the tutor's reply aloud, in the target language.
function speak(text) {
    if (!voiceOn || !text || !window.speechSynthesis) return;
    const clean = String(text).replace(/\([^)]*\)/g, "").replace(/[""]/g, "").trim();
    if (!clean) return;
    const u = new SpeechSynthesisUtterance(clean);
    u.lang = targetTag;
    u.rate = 0.95;
    u.onstart = () => setOrb("speaking", "🗣️", "Speaking… listen and repeat.");
    u.onend = () => setOrb("idle", "🙂", "Your turn — say something back.");
    u.onerror = () => setOrb("idle", "🙂", "Your turn.");
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
}

function addBubble(role, text, corrections = [], vocab = []) {
    const wrap = document.createElement("div");
    wrap.className = `bubble ${role}`;
    wrap.textContent = text;

    if (role === "tutor") {
        const bar = document.createElement("button");
        bar.className = "speakBtn";
        bar.type = "button";
        bar.textContent = "🔊 hear it";
        bar.onclick = () => speak(text);
        wrap.appendChild(bar);
    }
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

async function sendMessage(text) {
    if (!text.trim()) return;
    addBubble("user", text);
    $("inMsg").value = "";
    $("btnSend").disabled = true;
    setOrb("thinking", "🤔", "Thinking…");
    try {
        const data = await api("/api/chat", { method: "POST", body: JSON.stringify({ message: text }) });
        addBubble("tutor", data.reply, data.corrections, data.vocab);
        renderStats(data.stats);
        loadReview();
        const clean = !data.corrections || !data.corrections.length;
        setOrb(clean ? "happy" : "oops", clean ? "😄" : "😅",
            clean ? "Nice — no fixes needed." : "One small fix, then onward.");
        speak(data.reply);
    } catch (e) {
        setOrb("error", "😵", e.message);
        addBubble("tutor", "⚠️ " + e.message);
    } finally {
        $("btnSend").disabled = false;
        $("inMsg").focus();
    }
}

async function newPrompt() {
    const topic = $("inTopic").value.trim() || "everyday life";
    $("btnDrill").disabled = true;
    setOrb("thinking", "🤔", "Setting up a new topic…");
    try {
        const data = await api(`/api/drill?topic=${encodeURIComponent(topic)}`);
        addBubble("tutor", data.reply, data.corrections, data.vocab);
        setOrb("idle", "🙂", "Your turn — jump in.");
        speak(data.reply);
    } catch (e) {
        setOrb("error", "😵", e.message);
        addBubble("tutor", "⚠️ " + e.message);
    } finally {
        $("btnDrill").disabled = false;
    }
}

function showApp(learner) {
    $("setupCard").hidden = true;
    $("chatCard").hidden = false;
    $("btnReset").hidden = false;
    $("chatTitle").textContent = `Practising ${learner.language} with ${learner.name}`;
    targetTag = tagFor(learner.language);
    setOrb("idle", "🙂", `Ready when you are — let's practise ${learner.language}.`);
    renderStats(learner.stats);
}

// --- speech in: let the friend speak the language they're learning.
let recog = null;
let listening = false;

function initSpeech() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
        $("btnMic").title = "Speech input isn't supported in this browser (try Chrome or Edge)";
        return;
    }
    recog = new SR();
    recog.interimResults = false;
    recog.maxAlternatives = 1;
    recog.onresult = (e) => {
        const text = e.results[0][0].transcript;
        $("inMsg").value = text;
        sendMessage(text);
    };
    recog.onstart = () => {
        listening = true;
        $("btnMic").classList.add("live");
        setOrb("listening", "🎙️", "Listening… speak now.");
    };
    recog.onend = () => { listening = false; $("btnMic").classList.remove("live"); };
    recog.onerror = () => { listening = false; $("btnMic").classList.remove("live"); setOrb("idle", "🙂", "Didn't catch that — try again."); };
}

function toggleMic() {
    if (!recog) {
        addBubble("tutor", "🎤 Speech input isn't supported in this browser. Chrome or Edge work best.");
        return;
    }
    if (listening) { recog.stop(); return; }
    recog.lang = targetTag;
    try { recog.start(); } catch (_) { /* already started */ }
}

async function boot() {
    initSpeech();
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
$("btnMic").onclick = toggleMic;
$("btnVoice").onclick = () => {
    voiceOn = !voiceOn;
    $("btnVoice").textContent = voiceOn ? "🔊 voice on" : "🔇 voice off";
    if (!voiceOn && window.speechSynthesis) window.speechSynthesis.cancel();
};
$("inMsg").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage($("inMsg").value); }
});

boot();
