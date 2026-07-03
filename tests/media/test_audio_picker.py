from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.media import audio_picker


@pytest.fixture
def tmp_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    manifest = tmp_path / "audio_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "tracks": [
                    {"track_id": "chill-001", "filename": "chill/a.mp3", "theme_tags": ["chill"]},
                    {"track_id": "chill-002", "filename": "chill/b.mp3", "theme_tags": ["chill"]},
                    {"track_id": "upbeat-001", "filename": "upbeat/c.mp3", "theme_tags": ["upbeat"]},
                ]
            }
        )
    )
    (tmp_path / "chill").mkdir()
    (tmp_path / "upbeat").mkdir()
    (tmp_path / "chill" / "a.mp3").write_bytes(b"fake")
    (tmp_path / "chill" / "b.mp3").write_bytes(b"fake")
    (tmp_path / "upbeat" / "c.mp3").write_bytes(b"fake")
    history = tmp_path / "audio_history.json"
    monkeypatch.setattr(audio_picker, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(audio_picker, "AUDIO_ROOT", tmp_path)
    monkeypatch.setattr(audio_picker, "HISTORY_PATH", history)
    return tmp_path


def test_pick_returns_matching_theme(tmp_audio: Path) -> None:
    track = audio_picker.pick("upbeat")
    assert track.name == "c.mp3"


def test_pick_avoids_last_two_days(tmp_audio: Path) -> None:
    (tmp_audio / "audio_history.json").write_text(
        json.dumps(
            {
                "history": [
                    {"date": "2026-07-01", "track_ids": ["chill-001"]},
                    {"date": "2026-07-02", "track_ids": ["chill-001"]},
                ]
            }
        )
    )
    # First pick MUST be b.mp3 (chill-001 is in recent 2-day window).
    # After the pick, chill-002 lands in today's history, so a second
    # pick would exhaust filtered candidates and relax -- that's a
    # separate behavior tested in test_pick_relaxes_history_filter.
    track = audio_picker.pick("chill")
    assert track.name == "b.mp3"


def test_pick_raises_when_no_track_matches(tmp_audio: Path) -> None:
    with pytest.raises(audio_picker.NoTrackAvailableError):
        audio_picker.pick("cinematic")


def test_pick_relaxes_history_filter_when_all_recent(
    tmp_audio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Both chill tracks were used yesterday
    (tmp_audio / "audio_history.json").write_text(
        json.dumps(
            {"history": [{"date": "2026-07-02", "track_ids": ["chill-001", "chill-002"]}]}
        )
    )
    track = audio_picker.pick("chill")
    assert track.name in {"a.mp3", "b.mp3"}
