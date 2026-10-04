"""Prompt construction for the local open-weight tutor.

The model is asked to answer in a strict, easy-to-parse format so a single
local inference call produces the reply, gentle corrections, and new vocabulary
at once -- important when the model is running on a friend's laptop.
"""
from __future__ import annotations

_LEVEL_GUIDE = {
    "beginner": "Use very short A1/A2 sentences, present tense, high-frequency words. Always add an English translation in parentheses.",
    "intermediate": "Use everyday B1/B2 language, mix of tenses, and only translate unfamiliar words.",
    "advanced": "Use natural B2/C1 language, idioms, and do not translate unless asked.",
}


def tutor_system_prompt(language: str, level: str, learner: str, weak_items: list[str]) -> str:
    guide = _LEVEL_GUIDE.get(level, _LEVEL_GUIDE["beginner"])
    weak = ", ".join(weak_items[:8]) if weak_items else "none yet"

    return f"""You are LinguaPal, a warm, patient {language} tutor for your friend {learner}.
You run on a local open-weight model, so {learner}'s practice stays on their own machine.

Rules:
- Reply primarily in {language}. Level: {level}. {guide}
- Keep replies short (2-5 sentences) and end with ONE question to keep the conversation going.
- Be encouraging; correct mistakes kindly, never mock.
- Weave these phrases the learner keeps forgetting back in when natural: {weak}.

You MUST respond in EXACTLY this format and nothing else:

REPLY: <your reply in {language}, plus a short English tip if helpful>
CORRECTIONS: <one bullet per correction like "- 'yo soy cansado' -> 'estoy cansado' (use estar for states)" or NONE>
VOCAB: <term = translation>; <term = translation> | or NONE
"""


def drill_prompt(language: str, level: str, topic: str) -> str:
    return tutor_system_prompt(language, level, "the learner", []) + (
        f"\nToday's practice topic: {topic}. Open the conversation with a question about it."
    )
