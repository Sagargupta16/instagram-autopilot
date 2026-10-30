"""A claimed slot keeps trying until it posts: the asked pillar once more with a fresh topic,
then the evergreen pillars, for as long as each attempt fails before the publisher boundary.

The owner made a post a must on 2026-10-24: 9 of the 12 failed runs since 2026-10-10 ended
on a scene still invalid after its repair call, and nothing tried again that day. Only an
attempt whose receipt is back at "failed" moves on. One that reached the publisher boundary
is "uncertain" and stops the chain, so a publish call is never repeated (contracts 2 and 19).
Every later attempt claims its slot key again, so the daily cap, the minimum gap, the posting
window and the per-key attempt budget still apply.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Any

from src.slots.schedule import SlotPlan
from src.state.ledger import Ledger

log = logging.getLogger(__name__)

FALLBACK_PILLARS = ("tech-versus", "tech-explainer")  # evergreen formats that need no figures


class Failed(RuntimeError):
    """Every attempt in the plan failed before publishing; `key` is the last one tried."""

    def __init__(self, key: str) -> None:
        super().__init__(f"every attempt for {key.rsplit('|', 1)[0]} failed before publishing")
        self.key = key


def attempt_pillars(config: dict[str, Any], first: dict[str, Any]) -> list[dict[str, Any]]:
    """The asked pillar twice (each attempt draws a fresh topic), then each fallback once."""
    by_id = {pillar["id"]: pillar for pillar in config["pillars"]}
    fallbacks = [by_id[name] for name in FALLBACK_PILLARS if name in by_id and name != first["id"]]
    return [first, first, *fallbacks]


def _ready(ledger: Ledger | None, key: str, now: datetime, config: dict[str, Any]) -> bool:
    """Whether another attempt may start: always in a dry-run; otherwise inside the window
    and with the slot key claimed again under the cap, the gap and the attempt budget."""
    if ledger is None:
        return True
    cadence = config["cadence"]
    window = cadence["window_utc"]
    if not window["start"] <= now.strftime("%H:%M") < window["end"]:
        return False
    return ledger.claim(
        key,
        now,
        min_gap_minutes=cadence["min_gap_minutes"],
        max_posts_per_day=cadence["max_posts_per_day"],
    )


def _settled(ledger: Ledger | None, key: str, error: Exception, now: datetime) -> bool:
    """Record the failure; True when nothing reached Instagram, so trying again is safe."""
    if ledger is None:
        return True
    ledger.fail(key, type(error).__name__, now)
    return ledger.get(key).get("status") == "failed"


def post(
    slot: SlotPlan,
    key: str,
    *,
    attempt: Callable[[SlotPlan, str], str | None],
    ledger: Ledger | None,
    config: dict[str, Any],
    clock: Callable[[], datetime],
) -> tuple[str, str | None]:
    """The slot key and media ID of the first attempt that posts. `key` is already claimed;
    raises Failed (from the last error) when no attempt in the plan could post."""
    plan = attempt_pillars(config, slot.pillar)
    prefix, tried, last = key.rsplit("|", 1)[0], key, None
    for index, pillar in enumerate(plan):
        key = f"{prefix}|{pillar['id']}"
        if index and not _ready(ledger, key, clock(), config):
            break
        tried = key
        try:
            return key, attempt(replace(slot, pillar=pillar), key)
        except Exception as error:
            if not _settled(ledger, key, error, clock()):
                raise  # it may have reached Instagram: reconcile, never post again
            last = error
            if index + 1 < len(plan):
                log.warning(
                    "Attempt %d of %d (%s) failed before publishing (%s); trying %s next",
                    index + 1,
                    len(plan),
                    pillar["id"],
                    type(error).__name__,
                    plan[index + 1]["id"],
                )
    raise Failed(tried) from last
