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
MAX_HISTORY = 500


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
