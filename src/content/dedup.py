"""Post history dedup -- topics + recent image prompts so Claude avoids repeats.

History file structure (list of entries, newest appended last):
    [
        {"topic": "...", "image_prompts": ["...", "..."], "ts": "2026-05-05T..."},
        ...
    ]

Legacy format (list[str] of topics) is read transparently and migrated on next write.
Atomic writes (temp file + rename) prevent corruption if the process is killed mid-save.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
POSTED_TOPICS_FILE = DATA_DIR / "posted_topics.json"
POSTED_SLOTS_FILE = DATA_DIR / "posted_slots.json"
MAX_HISTORY = 500
MAX_SLOT_HISTORY = 90  # ~30 days at 3 slots/day


def _load_raw() -> list[dict[str, Any]]:
    """Load history, migrating legacy list[str] -> list[dict] in-memory."""
    if not POSTED_TOPICS_FILE.exists():
        return []
    data = json.loads(POSTED_TOPICS_FILE.read_text())
    if not data:
        return []
    # Legacy format: list[str] of topics -- wrap into new structure.
    if isinstance(data[0], str):
        return [{"topic": t, "image_prompts": [], "ts": ""} for t in data]
    return data


def load_posted_topics() -> list[str]:
    """Return topic strings in chronological order (oldest first)."""
    return [e["topic"] for e in _load_raw() if e.get("topic")]


def load_recent_image_prompts(limit: int = 25) -> list[str]:
    """Return the most recent image prompts, newest first, flattened across posts.

    Used by the caption prompt to tell Claude which scenes to AVOID repeating.
    """
    entries = _load_raw()
    prompts: list[str] = []
    for entry in reversed(entries):
        for p in reversed(entry.get("image_prompts") or []):
            prompts.append(p)
            if len(prompts) >= limit:
                return prompts
    return prompts


def record_post(topic: str, image_prompts: list[str] | None = None) -> None:
    """Append a post entry to history and atomically persist it."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    entries = _load_raw()
    entries.append(
        {
            "topic": topic,
            "image_prompts": list(image_prompts or []),
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    entries = entries[-MAX_HISTORY:]
    # Atomic write -- a kill between write and rename leaves the old file intact.
    tmp = POSTED_TOPICS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, indent=2))
    tmp.replace(POSTED_TOPICS_FILE)


def _slot_key(date_iso: str, time_utc: str, pillar_id: str) -> str:
    """Deterministic per-slot identifier used for same-day idempotency."""
    return f"{date_iso}|{time_utc}|{pillar_id}"


def load_posted_slots() -> set[str]:
    """Return the set of slot keys already published today (and recent days)."""
    if not POSTED_SLOTS_FILE.exists():
        return set()
    try:
        return set(json.loads(POSTED_SLOTS_FILE.read_text()))
    except json.JSONDecodeError:
        return set()


def slot_already_posted(date_iso: str, time_utc: str, pillar_id: str) -> bool:
    """True if a slot with the same (date, time, pillar) has already published."""
    return _slot_key(date_iso, time_utc, pillar_id) in load_posted_slots()


def record_slot(date_iso: str, time_utc: str, pillar_id: str) -> None:
    """Persist a slot key so re-runs on the same date skip it."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    slots = list(load_posted_slots())
    key = _slot_key(date_iso, time_utc, pillar_id)
    if key not in slots:
        slots.append(key)
    slots = slots[-MAX_SLOT_HISTORY:]
    tmp = POSTED_SLOTS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(slots, indent=2))
    tmp.replace(POSTED_SLOTS_FILE)
