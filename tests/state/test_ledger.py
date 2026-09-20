"""The publication ledger must protect real-world side effects across retries."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta

import pytest


def _ledger(tmp_path):
    try:
        module = importlib.import_module("src.state.ledger")
        storage = importlib.import_module("src.state.local")
    except ModuleNotFoundError:
        pytest.fail("A durable publication ledger is required before publishing")
    return module.Ledger(storage.LocalStore(tmp_path / "state.json"))


def test_only_one_worker_can_claim_a_slot(tmp_path):
    first = _ledger(tmp_path)
    second = _ledger(tmp_path)
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)
    assert first.claim("2026-09-20|12:00|food", now, min_gap_minutes=180)
    assert not second.claim("2026-09-20|12:00|food", now, min_gap_minutes=180)
    assert not second.claim("2026-09-20|12:30|travel", now, min_gap_minutes=180)


def test_confirmed_publication_survives_restart_and_enforces_gap(tmp_path):
    ledger = _ledger(tmp_path)
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)
    key = "2026-09-20|12:00|food"
    assert ledger.claim(key, now, min_gap_minutes=180)
    ledger.before_publish(key, "container-1", now)
    ledger.complete(key, "media-1", now)
    restarted = _ledger(tmp_path)
    assert restarted.get(key)["media_id"] == "media-1"
    assert not restarted.claim(key, now + timedelta(hours=4), min_gap_minutes=180)
    assert not restarted.claim(
        "2026-09-20|13:00|tech", now + timedelta(hours=1), min_gap_minutes=180
    )
    assert restarted.claim("2026-09-20|16:00|tech", now + timedelta(hours=4), min_gap_minutes=180)


def test_lost_publish_response_cannot_trigger_a_second_post(tmp_path):
    ledger = _ledger(tmp_path)
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)
    key = "2026-09-20|12:00|food"
    assert ledger.claim(key, now, min_gap_minutes=180)
    ledger.before_publish(key, "container-1", now)
    ledger.fail(key, "network timeout", now)
    assert ledger.get(key)["status"] == "uncertain"
    assert not ledger.claim(key, now + timedelta(days=1), min_gap_minutes=180)
    assert not ledger.claim("2026-09-21|12:00|food", now + timedelta(days=1), min_gap_minutes=180)


def test_generation_failure_can_retry_but_expired_preparation_is_safe(tmp_path):
    ledger = _ledger(tmp_path)
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)
    key = "2026-09-20|12:00|food"
    assert ledger.claim(key, now, min_gap_minutes=180)
    ledger.fail(key, "image failed", now)
    assert ledger.get(key)["status"] == "failed"
    assert ledger.claim(key, now + timedelta(minutes=20), min_gap_minutes=180)
    assert ledger.claim(key, now + timedelta(hours=2), min_gap_minutes=180)


def test_superseded_worker_cannot_publish_after_lease_recovery(tmp_path):
    first = _ledger(tmp_path)
    second = _ledger(tmp_path)
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)
    key = "2026-09-20|12:00|food"
    assert first.claim(key, now, min_gap_minutes=180)
    assert second.claim(key, now + timedelta(hours=2), min_gap_minutes=180)
    with pytest.raises(RuntimeError, match="ownership"):
        first.before_publish(key, "old-container", now + timedelta(hours=2))


def test_explicit_resolution_releases_uncertain_outcome(tmp_path):
    ledger = _ledger(tmp_path)
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)
    key = "2026-09-20|12:00|food"
    assert ledger.claim(key, now, min_gap_minutes=180)
    ledger.before_publish(key, "container-1", now)
    ledger.fail(key, "timeout", now)
    ledger.resolve(key, media_id="confirmed-media", now=now)
    assert ledger.get(key)["status"] == "published"
    assert ledger.get(key)["media_id"] == "confirmed-media"


def test_corrupt_state_fails_closed(tmp_path):
    (tmp_path / "state.json").write_text('{"slots": "corrupt"}')
    ledger = _ledger(tmp_path)
    with pytest.raises(ValueError, match="state"):
        ledger.claim("slot", datetime.now(UTC), min_gap_minutes=180)


def test_generation_retries_have_a_spending_limit(tmp_path):
    ledger = _ledger(tmp_path)
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)
    key = "2026-09-20|12:00|food"
    for _ in range(3):
        assert ledger.claim(key, now, min_gap_minutes=180)
        ledger.fail(key, "provider down", now)
    assert not ledger.claim(key, now, min_gap_minutes=180)


def test_daily_limit_survives_plan_or_config_change(tmp_path):
    ledger = _ledger(tmp_path)
    now = datetime(2026, 9, 20, 8, tzinfo=UTC)
    for hour in (8, 12):
        current = now.replace(hour=hour)
        key = f"2026-09-20|{hour:02}:00|food"
        assert ledger.claim(key, current, min_gap_minutes=180, max_posts_per_day=2)
        ledger.before_publish(key, f"container-{hour}", current)
        ledger.complete(key, f"media-{hour}", current)
    assert not ledger.claim(
        "2026-09-20|18:00|new-pillar",
        now.replace(hour=18),
        min_gap_minutes=180,
        max_posts_per_day=2,
    )
