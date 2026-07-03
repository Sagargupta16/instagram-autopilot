"""Pick a royalty-free audio track for a Reel, avoiding recent repeats.

Reads assets/audio/audio_manifest.json (curated once via
scripts/curate_audio.py) and assets/cache/audio_history.json (last-N-days
picks). Filters manifest to entries whose theme_tags contain the
requested theme AND whose track_id is not in the recent-days window;
random-picks; atomically appends to history.

Raises NoTrackAvailableError when the manifest is empty for the theme
(e.g. curation script hasn't run yet). Callers -- specifically
reel_flow -- catch this and publish silent-reel as fallback.
"""

from __future__ import annotations

import json
import logging
import os
import random
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

AUDIO_ROOT = Path(__file__).resolve().parent.parent.parent / "assets" / "audio"
MANIFEST_PATH = AUDIO_ROOT / "audio_manifest.json"
HISTORY_PATH = (
    Path(__file__).resolve().parent.parent.parent / "assets" / "cache" / "audio_history.json"
)
HISTORY_LOOKBACK_DAYS = 2


class NoTrackAvailableError(Exception):
    """No manifest track matches the requested theme."""


def _load_manifest() -> list[dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        return []
    try:
        return json.loads(MANIFEST_PATH.read_text()).get("tracks", [])
    except json.JSONDecodeError:
        log.warning("audio manifest corrupt")
        return []


def _load_history() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text()).get("history", [])
    except json.JSONDecodeError:
        log.warning("audio history corrupt, resetting")
        return []


def _recent_track_ids(history: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for entry in history[-HISTORY_LOOKBACK_DAYS:]:
        ids.update(entry.get("track_ids", []))
    return ids


def _append_history(track_id: str) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = _load_history()
    today = datetime.now(UTC).date().isoformat()
    if history and history[-1]["date"] == today:
        history[-1]["track_ids"].append(track_id)
    else:
        history.append({"date": today, "track_ids": [track_id]})
    fd, tmp = tempfile.mkstemp(dir=HISTORY_PATH.parent, suffix=".json")
    os.close(fd)
    Path(tmp).write_text(json.dumps({"history": history[-30:]}, indent=2))
    Path(tmp).replace(HISTORY_PATH)


def pick(theme: str) -> Path:
    """Return path to a track matching `theme`, not used in last 2 days."""
    manifest = _load_manifest()
    recent = _recent_track_ids(_load_history())
    candidates = [
        t
        for t in manifest
        if theme in t.get("theme_tags", []) and t["track_id"] not in recent
    ]
    if not candidates:
        candidates = [t for t in manifest if theme in t.get("theme_tags", [])]
    if not candidates:
        raise NoTrackAvailableError(f"No tracks matching theme '{theme}' in manifest")
    # NOSONAR python:S2245 -- track selection is NOT a security context;
    # we want easy variety across days, not cryptographic randomness.
    chosen = random.choice(candidates)  # NOSONAR
    _append_history(chosen["track_id"])
    return AUDIO_ROOT / chosen["filename"]
