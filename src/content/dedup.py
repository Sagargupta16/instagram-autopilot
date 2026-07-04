"""Post history dedup -- topics + recent image prompts so Claude avoids repeats.

History file structure (list of entries, newest appended last):
    [
        {"topic": "...", "image_prompts": [...], "ts": "...", "slot_key": "..."},
        ...
    ]

`slot_key` is the format YYYY-MM-DD|HH:MM|pillar-id. It lets a re-run on
the same date (workflow_dispatch replays the same seeded plan) skip
slots that already published. Older entries without slot_key are read
transparently.

Legacy format (list[str] of topics) is also read transparently and
migrated on next write.

Only ONE persisted file (posted_topics.json) so the daily-post workflow's
existing "Persist post history" git-add step covers both post history
AND slot idempotency. Atomic writes prevent corruption on process kill.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
POSTED_TOPICS_FILE = DATA_DIR / "posted_topics.json"
MAX_HISTORY = 500


def _load_raw() -> list[dict[str, Any]]:
    """Load history, migrating legacy list[str] -> list[dict] in-memory."""
    if not POSTED_TOPICS_FILE.exists():
        return []
    data = json.loads(POSTED_TOPICS_FILE.read_text())
    if not data:
        return []
    if isinstance(data[0], str):
        return [{"topic": t, "image_prompts": [], "ts": ""} for t in data]
    return data


def load_posted_topics() -> list[str]:
    """Return topic strings in chronological order (oldest first)."""
    return [e["topic"] for e in _load_raw() if e.get("topic")]


def load_recent_image_prompts(limit: int = 25) -> list[str]:
    """Return the most recent image prompts, newest first, flattened across posts."""
    entries = _load_raw()
    prompts: list[str] = []
    for entry in reversed(entries):
        for p in reversed(entry.get("image_prompts") or []):
            prompts.append(p)
            if len(prompts) >= limit:
                return prompts
    return prompts


def _atomic_write(entries: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = POSTED_TOPICS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries[-MAX_HISTORY:], indent=2))
    tmp.replace(POSTED_TOPICS_FILE)


def record_post(topic: str, image_prompts: list[str] | None = None) -> None:
    """Append a post entry to history and atomically persist it."""
    entries = _load_raw()
    entries.append(
        {
            "topic": topic,
            "image_prompts": list(image_prompts or []),
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    _atomic_write(entries)


def _slot_key(date_iso: str, time_utc: str, pillar_id: str) -> str:
    """Deterministic per-slot identifier used for same-day idempotency."""
    return f"{date_iso}|{time_utc}|{pillar_id}"


def slot_already_posted(date_iso: str, time_utc: str, pillar_id: str) -> bool:
    """True if any prior post entry carries the same (date, time, pillar) key."""
    key = _slot_key(date_iso, time_utc, pillar_id)
    return any(e.get("slot_key") == key for e in _load_raw())


def record_slot(date_iso: str, time_utc: str, pillar_id: str) -> None:
    """Stamp today's slot_key onto the MOST RECENT topic entry.

    Called by main.run() right after _run_slot() succeeds -- so the
    newest entry is the one we just published. Attaching the slot_key
    to that entry means slot idempotency rides posted_topics.json's
    existing persistence path (no separate file, no separate git-add).
    """
    entries = _load_raw()
    if not entries:
        # Should not happen -- record_post ran first. Defensive: append a stub.
        entries.append(
            {
                "topic": "",
                "image_prompts": [],
                "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                "slot_key": _slot_key(date_iso, time_utc, pillar_id),
            }
        )
        _atomic_write(entries)
        return
    entries[-1]["slot_key"] = _slot_key(date_iso, time_utc, pillar_id)
    _atomic_write(entries)
