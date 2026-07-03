"""Deterministic per-day posting schedule.

Given today's date, RNG-picks how many posts (0..max), what times (within
window, min-gap-enforced), and which pillar per slot. Seeded on YYYYMMDD
so re-runs on the same date produce the same plan (safe under CI retry).

apply_jitter() lives on as an intra-slot randomizer for callers that want
0..N-min sleeps before publishing.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlotPlan:
    time_utc: str  # "HH:MM"
    pillar: dict[str, Any]
    skip: bool


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


def apply_jitter(max_minutes: int) -> None:
    """Sleep a random 0..max_minutes."""
    if max_minutes <= 0:
        return
    sleep_sec = random.randint(0, max_minutes * 60)
    log.info(
        "Jitter: sleeping %d min %d sec before posting",
        sleep_sec // 60,
        sleep_sec % 60,
    )
    time.sleep(sleep_sec)


def plan_today(
    today: date,
    cadence: dict[str, Any],
    pillars: list[dict[str, Any]],
) -> list[SlotPlan]:
    """Return today's SlotPlans, deterministic on `today`."""
    if not pillars:
        return []
    rng = random.Random(int(today.strftime("%Y%m%d")))
    probs = cadence.get("post_probability", [0.15, 0.35, 0.35, 0.15])
    max_n = int(cadence.get("max_posts_per_day", 3))
    n = min(rng.choices(list(range(len(probs))), weights=probs)[0], max_n)
    if n == 0:
        return []
    window = cadence.get("window_utc", {})
    start = to_minutes(window.get("start", "04:00"))
    end = to_minutes(window.get("end", "20:00"))
    gap = int(cadence.get("min_gap_minutes", 90))
    slots: list[int] = []
    for _ in range(50):
        if len(slots) == n:
            break
        cand = rng.randint(start, end)
        if all(abs(cand - s) >= gap for s in slots):
            slots.append(cand)
    slots.sort()
    weights = [float(p.get("weight", 1.0)) for p in pillars]
    skip_p = float(cadence.get("skip_probability", 0.05))
    return [
        SlotPlan(
            time_utc=to_hhmm(m),
            pillar=rng.choices(pillars, weights=weights)[0],
            skip=(rng.random() < skip_p),
        )
        for m in slots
    ]
