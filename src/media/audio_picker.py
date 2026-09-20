"""Select local licensed audio without writes; record use after publication."""

from __future__ import annotations

import json
import os
import random
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from src.media.audio_manifest import AudioTrack, validate_track

AUDIO_ROOT = Path(__file__).resolve().parents[2] / "assets" / "audio"
MANIFEST_PATH = AUDIO_ROOT / "audio_manifest.json"
HISTORY_PATH = Path(__file__).resolve().parents[2] / "assets" / "cache" / "audio_history.json"
HISTORY_LOOKBACK_DAYS = 2


class NoTrackAvailableError(Exception):
    """No usable local track matches the requested theme."""


def _load_list(path: Path, key: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get(key, []) if isinstance(data, dict) else []
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    except (OSError, ValueError):
        return []


def _load_manifest() -> list[dict[str, Any]]:
    return _load_list(MANIFEST_PATH, "tracks")


def _load_history() -> list[dict[str, Any]]:
    return _load_list(HISTORY_PATH, "history")


def _recent_track_ids(history: list[dict[str, Any]]) -> set[str]:
    today = datetime.now(UTC).date()
    ids: set[str] = set()
    for entry in history:
        try:
            age = (today - date.fromisoformat(entry["date"])).days
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= age <= HISTORY_LOOKBACK_DAYS:
            track_ids = entry.get("track_ids", [])
            if isinstance(track_ids, list):
                ids.update(value for value in track_ids if isinstance(value, str))
    return ids


def _append_history(track_id: str) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = _load_history()
    history.append({"date": datetime.now(UTC).date().isoformat(), "track_ids": [track_id]})
    descriptor, temporary = tempfile.mkstemp(dir=HISTORY_PATH.parent, suffix=".json")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"history": history[-500:]}, stream, indent=2)
        Path(temporary).replace(HISTORY_PATH)
    finally:
        Path(temporary).unlink(missing_ok=True)


def select(theme: str) -> AudioTrack:
    """Read-only selection; missing, empty, unsafe or uncredited files are excluded."""
    candidates: list[AudioTrack] = []
    for entry in _load_manifest():
        try:
            track = validate_track(entry, AUDIO_ROOT)
        except (ValueError, OSError):
            continue
        if theme in entry["theme_tags"]:
            candidates.append(track)
    if not candidates:
        raise NoTrackAvailableError(f"No usable local audio for theme '{theme}'")
    recent = _recent_track_ids(_load_history())
    fresh = [track for track in candidates if track.track_id not in recent]
    return random.choice(fresh or candidates)  # NOSONAR -- editorial variety, not security.


def record_usage(track: AudioTrack) -> None:
    _append_history(track.track_id)


def pick(theme: str, *, record: bool = True) -> Path:
    """Compatibility API; use select() for preflight or dry-run."""
    track = select(theme)
    if record:
        record_usage(track)
    return track.path
