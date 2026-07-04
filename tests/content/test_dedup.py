"""Tests for posted-history dedup (topics + image prompts)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from src.content import dedup


@pytest.fixture()
def tmp_history(tmp_path: Path) -> Iterator[Path]:
    """Redirect dedup module to a temp history file for the test."""
    file = tmp_path / "posted_topics.json"
    with (
        patch.object(dedup, "DATA_DIR", tmp_path),
        patch.object(dedup, "POSTED_TOPICS_FILE", file),
    ):
        yield file


class TestRecordAndLoad:
    def test_empty_history_returns_empty(self, tmp_history: Path) -> None:
        assert dedup.load_posted_topics() == []
        assert dedup.load_recent_image_prompts() == []

    def test_record_then_load_topic(self, tmp_history: Path) -> None:
        dedup.record_post("my topic", ["slide1 prompt", "slide2 prompt"])
        assert dedup.load_posted_topics() == ["my topic"]

    def test_record_stores_image_prompts(self, tmp_history: Path) -> None:
        dedup.record_post("topic A", ["prompt 1", "prompt 2", "prompt 3"])
        dedup.record_post("topic B", ["prompt 4", "prompt 5"])
        prompts = dedup.load_recent_image_prompts(limit=10)
        # Newest first, flattened -- prompt 5 is most recent.
        assert prompts[0] == "prompt 5"
        assert "prompt 1" in prompts
        assert len(prompts) == 5

    def test_load_recent_respects_limit(self, tmp_history: Path) -> None:
        dedup.record_post("topic", [f"p{i}" for i in range(10)])
        assert len(dedup.load_recent_image_prompts(limit=3)) == 3

    def test_record_caps_at_max_history(self, tmp_history: Path) -> None:
        with patch.object(dedup, "MAX_HISTORY", 5):
            for i in range(10):
                dedup.record_post(f"topic {i}", [])
            topics = dedup.load_posted_topics()
            assert len(topics) == 5
            assert topics[-1] == "topic 9"
            assert topics[0] == "topic 5"

    def test_migrates_legacy_list_of_strings(self, tmp_history: Path) -> None:
        # Legacy format was a bare list[str] of topics.
        tmp_history.write_text(json.dumps(["legacy1", "legacy2"]))
        assert dedup.load_posted_topics() == ["legacy1", "legacy2"]
        # Legacy entries have no image prompts.
        assert dedup.load_recent_image_prompts() == []
        # Writing a new entry promotes the file to the new structure.
        dedup.record_post("new", ["p"])
        raw = json.loads(tmp_history.read_text())
        assert isinstance(raw[0], dict)
        assert raw[0]["topic"] == "legacy1"
        assert raw[-1]["topic"] == "new"
        assert raw[-1]["image_prompts"] == ["p"]

    def test_atomic_write_leaves_no_tmp_file(self, tmp_history: Path) -> None:
        dedup.record_post("t", ["p"])
        tmps = list(tmp_history.parent.glob("*.tmp"))
        assert tmps == []


class TestSlotIdempotency:
    def test_unrecorded_slot_is_not_posted(self, tmp_history: Path) -> None:
        assert dedup.slot_already_posted("2026-07-04", "06:00", "travel-cinematic") is False

    def test_recorded_slot_is_detected(self, tmp_history: Path) -> None:
        dedup.record_post("today's topic", ["p1"])
        dedup.record_slot("2026-07-04", "06:00", "travel-cinematic")
        assert dedup.slot_already_posted("2026-07-04", "06:00", "travel-cinematic") is True

    def test_different_slot_key_not_detected(self, tmp_history: Path) -> None:
        dedup.record_post("t", ["p"])
        dedup.record_slot("2026-07-04", "06:00", "travel-cinematic")
        assert dedup.slot_already_posted("2026-07-04", "12:00", "travel-cinematic") is False
        assert dedup.slot_already_posted("2026-07-05", "06:00", "travel-cinematic") is False
        assert dedup.slot_already_posted("2026-07-04", "06:00", "food-editorial-carousel") is False

    def test_record_slot_stamps_last_entry(self, tmp_history: Path) -> None:
        dedup.record_post("earlier topic", ["p1"])
        dedup.record_post("just-published topic", ["p2"])
        dedup.record_slot("2026-07-04", "06:00", "travel-cinematic")
        raw = json.loads(tmp_history.read_text())
        assert raw[-1]["topic"] == "just-published topic"
        assert raw[-1]["slot_key"] == "2026-07-04|06:00|travel-cinematic"
        assert "slot_key" not in raw[-2]

    def test_record_slot_survives_history_wipe(self, tmp_history: Path) -> None:
        # Simulates workflow_dispatch replay: same seeded plan produces same slot_key,
        # so second call sees the first's slot_key still committed in the file.
        dedup.record_post("run 1 topic", ["p"])
        dedup.record_slot("2026-07-04", "06:00", "travel-cinematic")

        # Fresh runner (state comes from committed file only)
        assert dedup.slot_already_posted("2026-07-04", "06:00", "travel-cinematic") is True
