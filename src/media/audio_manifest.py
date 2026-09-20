"""Validated local audio metadata shared by selection and explicit imports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

THEMES = ("chill", "upbeat", "cinematic", "ambient", "energetic")


@dataclass(frozen=True)
class AudioTrack:
    track_id: str
    path: Path
    attribution: str = ""


def validate_track(entry: dict[str, Any], root: Path) -> AudioTrack:
    if not isinstance(entry, dict):
        raise ValueError("Audio entry must be an object")
    track_id, filename = entry.get("track_id"), entry.get("filename")
    themes = entry.get("theme_tags")
    if not isinstance(track_id, str) or not track_id.strip():
        raise ValueError("Audio track_id must be nonempty")
    if not isinstance(filename, str) or not filename:
        raise ValueError("Audio filename must be nonempty")
    if not isinstance(themes, list) or not themes or any(theme not in THEMES for theme in themes):
        raise ValueError("Audio theme_tags must contain supported themes")
    path = (root / filename).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix.lower() not in {
        ".mp3",
        ".m4a",
        ".wav",
    }:
        raise ValueError("Audio path must stay within the audio library")
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Audio asset is missing or empty")
    attribution = entry.get("attribution", "")
    requires_credit = entry.get("attribution_required") or str(
        entry.get("license", "")
    ).upper().startswith("CC-BY")
    if not isinstance(attribution, str) or (requires_credit and not attribution.strip()):
        raise ValueError("Audio attribution is required by this license")
    return AudioTrack(track_id, path, attribution.strip())
