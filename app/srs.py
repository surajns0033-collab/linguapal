"""A tiny, dependency-free spaced-repetition scheduler (SM-2 inspired).

Keeping this local means the learner's study history never leaves the machine,
and the review schedule keeps working with zero internet access.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

# How long until a card is shown again, by repetition count (seconds).
_INTERVALS = [0, 6 * 60 * 60, 24 * 60 * 60, 3 * 24 * 60 * 60, 7 * 24 * 60 * 60,
              16 * 24 * 60 * 60, 35 * 24 * 60 * 60]


@dataclass
class CardState:
    ease: float = 2.5
    interval: float = 0.0
    reps: int = 0
    lapses: int = 0


def review(state: CardState, quality: int, now: float | None = None) -> tuple[CardState, float]:
    """Apply a grading (0=again, 1=hard, 2=good, 3=easy) and return new state + due_at."""
    now = time.time() if now is None else now
    quality = max(0, min(3, quality))

    if quality == 0:
        state.reps = 0
        state.lapses += 1
        state.interval = 10 * 60  # try again in 10 minutes
        state.ease = max(1.3, state.ease - 0.2)
    else:
        state.reps += 1
        if quality == 1:
            state.ease = max(1.3, state.ease - 0.15)
            factor = 1.2
        elif quality == 3:
            state.ease = min(3.2, state.ease + 0.15)
            factor = state.ease * 1.3
        else:  # good
            factor = state.ease

        base = _INTERVALS[min(state.reps, len(_INTERVALS) - 1)]
        state.interval = max(base * factor, 60 * 60)

    return state, now + state.interval
