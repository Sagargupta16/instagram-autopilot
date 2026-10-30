"""A claimed slot keeps trying until it posts, but never after Instagram may have the post."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.slots import post_attempts
from src.slots.schedule import SlotPlan
from src.state.ledger import Ledger
from src.state.local import LocalStore

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
PILLARS = [{"id": name} for name in ("cool-stats", "tech-explainer", "tech-versus")]
CONFIG = {
    "pillars": PILLARS,
    "cadence": {
        "window_utc": {"start": "04:00", "end": "20:00"},
        "min_gap_minutes": 180,
        "max_posts_per_day": 2,
    },
}
FIRST = "2026-10-24|12:00|cool-stats"


@pytest.fixture
def ledger(tmp_path) -> Ledger:
    store = Ledger(LocalStore(tmp_path / "state.json"))
    assert store.claim(FIRST, NOW, min_gap_minutes=180)
    return store


def post(ledger, attempt, clock=lambda: NOW):
    slot = SlotPlan("12:00", PILLARS[0], False)
    return post_attempts.post(
        slot, FIRST, attempt=attempt, ledger=ledger, config=CONFIG, clock=clock
    )


def test_the_plan_retries_the_pillar_then_the_evergreen_ones() -> None:
    plan = post_attempts.attempt_pillars(CONFIG, PILLARS[0])
    assert [p["id"] for p in plan] == ["cool-stats", "cool-stats", "tech-versus", "tech-explainer"]
    versus = post_attempts.attempt_pillars(CONFIG, PILLARS[2])
    assert [p["id"] for p in versus] == ["tech-versus", "tech-versus", "tech-explainer"]


def test_a_failure_before_publishing_moves_on_until_one_posts(ledger) -> None:
    tried = []

    def attempt(slot, key):
        tried.append(key)
        if slot.pillar["id"] == "cool-stats":
            raise ValueError("scene still invalid after two repairs")
        return "media-1"

    key, media_id = post(ledger, attempt)
    assert (key, media_id) == ("2026-10-24|12:00|tech-versus", "media-1")
    assert tried == [FIRST, FIRST, key]
    assert ledger.get(FIRST)["status"] == "failed"
    assert ledger.get(FIRST)["attempts"] == 2
    assert ledger.get(key)["status"] == "preparing"  # the caller completes it


def test_a_failure_after_the_publish_checkpoint_never_tries_again(ledger) -> None:
    tried = []

    def attempt(slot, key):
        tried.append(key)
        ledger.before_publish(key, "container-1", NOW)
        raise TimeoutError("publish response lost")

    with pytest.raises(TimeoutError):
        post(ledger, attempt)
    assert tried == [FIRST]
    assert ledger.get(FIRST)["status"] == "uncertain"


def test_every_attempt_failing_raises_failed_with_the_last_key(ledger) -> None:
    def attempt(slot, key):
        raise ValueError(f"no luck for {slot.pillar['id']}")

    with pytest.raises(post_attempts.Failed) as failure:
        post(ledger, attempt)
    assert failure.value.key == "2026-10-24|12:00|tech-explainer"
    assert isinstance(failure.value.__cause__, ValueError)


def test_no_retry_once_the_posting_window_has_closed(ledger) -> None:
    late = datetime(2026, 10, 24, 20, 5, tzinfo=UTC)
    tried = []

    def attempt(slot, key):
        tried.append(key)
        raise ValueError("invalid")

    with pytest.raises(post_attempts.Failed):
        post(ledger, attempt, clock=lambda: late)
    assert tried == [FIRST]


def test_a_dry_run_also_falls_back() -> None:
    def attempt(slot, key):
        if slot.pillar["id"] != "tech-explainer":
            raise ValueError("invalid")

    assert post(None, attempt) == ("2026-10-24|12:00|tech-explainer", None)
