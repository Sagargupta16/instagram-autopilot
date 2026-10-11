"""Which slot a run may fill: forced pillars, on-demand posts, and slot times already used."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.state.ledger import MAX_ATTEMPTS


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
