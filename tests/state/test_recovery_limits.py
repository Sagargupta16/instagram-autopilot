"""Long-lived state and killed workers must not defeat publication recovery."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from src.state.ledger import Ledger
from src.state.local import LocalStore
from src.state.store import empty_state


class SizedStore:
    def __init__(self):
        self.data = empty_state()

    def read(self):
        return json.loads(json.dumps(self.data)), None

    def save(self, data, revision):
        if len(json.dumps(data).encode()) > 900_000:
            raise ValueError("state too large")
        self.data = data


def test_large_valid_content_does_not_permanently_fill_the_store():
    store = SizedStore()
    ledger = Ledger(store)
    first = datetime(2026, 1, 1, 8, tzinfo=UTC)
    content = {
        "caption": "c" * 1800,
        "hashtags": "#" + "h" * 397,
        "image_prompts": ["p" * 1499 + str(i) for i in range(5)],
        "alt_texts": ["a" * 999 + str(i) for i in range(5)],
        "sources": [{"title": "t" * 500, "excerpt": "e" * 800, "url": "https://example.com"}] * 3,
    }
    for index in range(105):
        now = first + timedelta(days=index // 2, hours=4 * (index % 2))
        key = f"{now.date()}|{now:%H:%M}|food"
        assert ledger.claim(key, now, min_gap_minutes=180)
        ledger.remember(key, "topic", content, now)
        ledger.before_publish(key, f"container-{index}", now)
        ledger.complete(key, f"media-{index}", now)
    receipt = ledger.get("2026-01-01|08:00|food")
    assert receipt["media_id"] == "media-0"
    assert receipt["container_id"] == "container-0"
    assert len(json.dumps(store.data).encode()) < 900_000


def test_crash_exhaustion_becomes_failed_instead_of_silently_skipped(tmp_path):
    ledger = Ledger(LocalStore(tmp_path / "state.json"))
    now = datetime(2026, 9, 20, 8, tzinfo=UTC)
    key = "2026-09-20|08:00|food"
    for attempt in range(3):
        assert ledger.claim(key, now + timedelta(hours=2 * attempt), min_gap_minutes=180)
    assert not ledger.claim(key, now + timedelta(hours=6), min_gap_minutes=180)
    assert ledger.get(key)["status"] == "failed"
    assert ledger.get(key)["attempts"] == 3
