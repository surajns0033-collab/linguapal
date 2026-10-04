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
    weak = ", ".join(weak_items[:5]) if weak_items else "none"

    # Kept deliberately short: on a laptop GPU every extra prompt token is latency.
    return f"""You are LinguaPal, a warm {language} tutor for {learner} ({level}).
{guide}
Answer ONLY in this exact format, three labels each on their own line:
REPLY: <2-3 short {language} sentences, ending with one question>
CORRECTIONS: <"- 'wrong' -> 'right' (why)" per mistake, or NONE>
VOCAB: <term = translation>; <term = translation>, or NONE
Example:
REPLY: ¡Hola! ¿Cómo estás hoy? (Hi! How are you today?)
CORRECTIONS: - 'yo soy cansado' -> 'estoy cansado' (use estar for states)
VOCAB: cansado = tired; la mañana = the morning
Be encouraging, never mock. Reuse when natural: {weak}.
"""


def drill_prompt(language: str, level: str, topic: str) -> str:
    return tutor_system_prompt(language, level, "the learner", []) + (
        f"\nToday's practice topic: {topic}. Open the conversation with a question about it."
    )
