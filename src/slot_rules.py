"""Which slot a run may fill: forced pillars, on-demand posts, due candidates, the claim and
slot times already used; and which visual look the post gets."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any

from src.schedule import SlotPlan, plan_today
from src.state.ledger import MAX_ATTEMPTS, Ledger


def forced_pillar(config: dict[str, Any], pillar_id: str | None) -> dict[str, Any] | None:
    if pillar_id is None:
        return None
    for pillar in config["pillars"]:
        if pillar["id"] == pillar_id:
            return pillar
    known = ", ".join(pillar["id"] for pillar in config["pillars"])
    raise ValueError(f"Unknown pillar {pillar_id!r}; configured pillars: {known}")


def slot_time_used(slots: dict[str, Any], key: str) -> bool:
    """Another pillar already filled (or exhausted) this slot time, e.g. after --pillar."""
    prefix = key.rsplit("|", 1)[0] + "|"
    return any(
        other != key
        and other.startswith(prefix)
        and (
            entry["status"] in {"published", "publishing", "uncertain"}
            or entry.get("attempts", 0) >= MAX_ATTEMPTS
        )
        for other, entry in slots.items()
    )


def next_look(slots: dict[str, Any], count: int, today: date) -> int:
    """The look after the last published post's, so consecutive posts never share one; the
    day number picks it when no published receipt records a look (and in a dry-run)."""
    published = [
        entry
        for entry in slots.values()
        if entry.get("status") == "published" and isinstance(entry.get("look"), int)
    ]
    if not published:
        return today.toordinal() % count
    last = max(published, key=lambda entry: entry.get("published_at", ""))
    return (last["look"] + 1) % count


def post_now_refusal(slots: dict[str, Any], now: datetime, cadence: dict[str, Any]) -> str:
    """Why an on-demand post would break the window, the daily cap or the minimum gap."""
    window = cadence["window_utc"]
    if not window["start"] <= now.strftime("%H:%M") < window["end"]:
        return f"outside the posting window {window['start']}-{window['end']} UTC"
    published = [
        datetime.fromisoformat(entry["published_at"])
        for entry in slots.values()
        if entry["status"] == "published" and entry.get("published_at")
    ]
    today = [moment for moment in published if moment.date() == now.date()]
    if len(today) >= cadence["max_posts_per_day"]:
        return f"the daily cap of {cadence['max_posts_per_day']} posts is reached"
    gap = timedelta(minutes=cadence["min_gap_minutes"])
    if published and now - max(published) < gap:
        allowed = (max(published) + gap).strftime("%H:%M")
        return f"the minimum gap of {cadence['min_gap_minutes']} minutes runs until {allowed} UTC"
    return ""


def candidates(
    config: dict[str, Any],
    current: datetime,
    forced: dict[str, Any] | None,
    *,
    dry_run: bool,
    post_now: bool,
) -> list[SlotPlan]:
    """Due slots inside the window; with post_now (or a dry-run with none due) this minute."""
    window = config["cadence"]["window_utc"]
    due = [
        slot
        for slot in plan_today(current.date(), config["cadence"], config["pillars"])
        if not slot.skip
        and (
            dry_run or window["start"] <= slot.time_utc <= current.strftime("%H:%M") < window["end"]
        )
    ]
    if (dry_run and not due) or post_now:
        due = [SlotPlan(current.strftime("%H:%M"), forced or config["pillars"][0], False)]
    return [replace(slot, pillar=forced) for slot in due] if forced else due


def claimed(
    ledger: Ledger | None, slots: dict[str, Any], key: str, now: datetime, config: dict[str, Any]
) -> bool:
    """Whether this run now owns `key`: no other pillar used the slot time and the ledger claim
    (cap, gap, attempt budget) succeeded; always in a dry-run."""
    if slot_time_used(slots, key):
        return False
    if ledger is None:
        return True
    return ledger.claim(
        key,
        now,
        min_gap_minutes=config["cadence"]["min_gap_minutes"],
        max_posts_per_day=config["cadence"]["max_posts_per_day"],
    )
