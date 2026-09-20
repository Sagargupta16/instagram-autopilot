"""Legacy migration must preserve confirmed slots without inventing media IDs."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.content import dedup
from src.state.factory import create_ledger
from src.state.history import sync_history
from src.state.ledger import Ledger
from src.state.local import LocalStore
from src.state.store import ConflictError, empty_state, update


@pytest.fixture
def history(monkeypatch, tmp_path):
    monkeypatch.setattr(dedup, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dedup, "POSTED_TOPICS_FILE", tmp_path / "topics.json")
    return Ledger(LocalStore(tmp_path / "state.json"))


def test_migration_preserves_topics_and_blocks_a_legacy_slot(history):
    key = "2026-09-20|08:00|food"
    entries = [
        {
            "topic": "Legacy food",
            "image_prompts": ["old"],
            "ts": "2026-09-20T08:00:00+00:00",
            "slot_key": key,
        }
    ]
    dedup.POSTED_TOPICS_FILE.write_text(json.dumps(entries))
    sync_history(history)
    assert history.get(key)["status"] == "published"
    assert "media_id" not in history.get(key)
    assert history.get(key)["published_at"] == "2026-09-20T08:20:00+00:00"
    assert not history.claim(key, datetime(2026, 9, 20, 18, tzinfo=UTC), min_gap_minutes=180)
    assert dedup.load_posted_topics() == ["Legacy food"]


def test_remote_history_restores_to_a_new_runner_without_duplicates(history):
    dedup.record_post("older", ["old scene"])
    sync_history(history)
    instant = datetime(2026, 9, 20, 12, tzinfo=UTC)
    assert history.claim("new", instant, min_gap_minutes=180)
    history.remember(
        "new", "newer", {"caption": "caption", "image_prompts": ["new scene"]}, instant
    )
    sync_history(history)
    sync_history(history)
    assert dedup.load_posted_topics() == ["older", "newer"]
    assert dedup.load_recent_image_prompts()[0] == "new scene"


def test_cas_retry_preserves_another_writers_data():
    class RacingStore:
        def __init__(self):
            self.data = empty_state()
            self.saves = 0

        def read(self):
            return json.loads(json.dumps(self.data)), str(self.saves)

        def save(self, data, revision):
            self.saves += 1
            if self.saves == 1:
                self.data["history"].append({"topic": "other worker"})
                raise ConflictError("raced")
            self.data = data

    store = RacingStore()
    update(store, lambda data: data["history"].append({"topic": "this worker"}))
    assert [entry["topic"] for entry in store.data["history"]] == ["other worker", "this worker"]


def test_hosted_run_cannot_silently_use_ephemeral_state(monkeypatch):
    from src.settings import settings

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(settings, "state_backend", "local")
    with pytest.raises(ValueError, match="STATE_BACKEND=github"):
        create_ledger()


def test_github_backend_requires_explicit_credentials(monkeypatch):
    from src.settings import settings

    monkeypatch.setattr(settings, "state_backend", "github")
    monkeypatch.setattr(settings, "state_repository", "owner/repo")
    monkeypatch.setattr(settings, "state_github_token", "")
    with pytest.raises(ValueError):
        create_ledger()
