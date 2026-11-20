"""Simple SM-2-lite spaced-review schedule (no efficacy claims)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

ReviewGrade = Literal["again", "hard", "good", "easy"]


@dataclass(frozen=True, slots=True)
class ScheduleState:
    interval_days: float
    ease_factor: float
    repetitions: int
    due_at: datetime
    last_result: ReviewGrade


def initial_schedule(*, now: datetime | None = None) -> ScheduleState:
    ts = now or datetime.now(UTC)
    return ScheduleState(
        interval_days=0.0,
        ease_factor=2.5,
        repetitions=0,
        due_at=ts,
        last_result="again",
    )


def advance_schedule(
    *,
    interval_days: float,
    ease_factor: float,
    repetitions: int,
    grade: ReviewGrade,
    now: datetime | None = None,
) -> ScheduleState:
    """
    Lightweight SM-2 variant for flashcard/quiz review.

    Intervals are scheduling hints only — not evidence of learning gain.
    """
    ts = now or datetime.now(UTC)
    ef = max(1.3, float(ease_factor))
    reps = int(repetitions)
    interval = float(interval_days)

    if grade == "again":
        reps = 0
        interval = 0.0
        ef = max(1.3, ef - 0.2)
    elif grade == "hard":
        reps = max(0, reps)
        interval = max(1.0, interval * 1.2) if reps > 0 else 1.0
        ef = max(1.3, ef - 0.15)
        reps += 1
    elif grade == "good":
        if reps == 0:
            interval = 1.0
        elif reps == 1:
            interval = 3.0
        else:
            interval = max(1.0, interval * ef)
        reps += 1
    else:  # easy
        if reps == 0:
            interval = 2.0
        elif reps == 1:
            interval = 5.0
        else:
            interval = max(1.0, interval * ef * 1.3)
        ef = min(3.0, ef + 0.15)
        reps += 1

    due = ts + timedelta(days=interval if interval > 0 else 0)
    if interval <= 0:
        due = ts + timedelta(minutes=10)

    return ScheduleState(
        interval_days=round(interval, 4),
        ease_factor=round(ef, 4),
        repetitions=reps,
        due_at=due,
        last_result=grade,
    )
