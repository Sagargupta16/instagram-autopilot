"""Exercise orchestration with real local state and mocked service boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from src import main
from src.content import dedup
from src.schedule import SlotPlan
from src.state.ledger import Ledger
from src.state.local import LocalStore

NOW = datetime(2026, 9, 20, 12, tzinfo=UTC)


@pytest.fixture
def runner(monkeypatch, tmp_path, sample_config, sample_caption_data):
    monkeypatch.chdir(tmp_path)
    ledger = Ledger(LocalStore(tmp_path / "publication.json"))
    monkeypatch.setattr(main, "create_ledger", lambda: ledger, raising=False)
    monkeypatch.setattr(main, "load_config", lambda: sample_config)
    monkeypatch.setattr(main, "_preflight_all_auth", Mock())
    monkeypatch.setattr(main.cloudinary_host, "configure", Mock())
    monkeypatch.setattr(
        main,
        "generate_topic_brief",
        Mock(return_value={"topic": "fresh", "sources": []}),
        raising=False,
    )
    monkeypatch.setattr(main, "generate_caption", Mock(return_value=sample_caption_data))
    monkeypatch.setattr(dedup, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dedup, "POSTED_TOPICS_FILE", tmp_path / "topics.json")
    slots = [SlotPlan("10:00", sample_config["pillars"][0], False)]
    monkeypatch.setattr(main, "plan_today", lambda *args: slots)
    return ledger, slots


def test_failed_slot_propagates_failure_and_is_not_marked_published(runner, monkeypatch):
    ledger, slots = runner
    monkeypatch.setattr(main, "post_carousel", Mock(side_effect=RuntimeError("generation failed")))
    with pytest.raises(RuntimeError, match="failed"):
        main.run(now=NOW)
    assert ledger.get(f"2026-09-20|10:00|{slots[0].pillar['id']}")["status"] == "failed"


def test_published_media_id_is_persisted_before_success(runner, monkeypatch):
    ledger, slots = runner

    def publish(*args, before_publish, **kwargs):
        before_publish("parent-container")
        return "media-123"

    monkeypatch.setattr(main, "post_carousel", publish)
    main.run(now=NOW)
    key = f"2026-09-20|10:00|{slots[0].pillar['id']}"
    assert ledger.get(key)["status"] == "published"
    assert ledger.get(key)["media_id"] == "media-123"


def test_one_tick_never_bursts_multiple_overdue_posts(runner, monkeypatch):
    _, slots = runner
    slots.append(SlotPlan("11:00", slots[0].pillar, False))

    def publish(*args, before_publish, **kwargs):
        before_publish("container")
        return "media"

    publish_mock = Mock(side_effect=publish)
    monkeypatch.setattr(main, "post_carousel", publish_mock)
    main.run(now=NOW)
    main.run(now=NOW + timedelta(minutes=20))
    assert publish_mock.call_count == 1
    main.run(now=NOW + timedelta(hours=3))
    assert publish_mock.call_count == 2


def test_future_slot_does_not_generate_or_preflight(runner, monkeypatch):
    _, slots = runner
    slots[:] = [SlotPlan("18:00", slots[0].pillar, False)]
    publish = Mock()
    monkeypatch.setattr(main, "post_carousel", publish)
    main.run(now=NOW)
    publish.assert_not_called()
    main._preflight_all_auth.assert_not_called()


def test_dry_run_never_constructs_or_mutates_durable_state(runner, monkeypatch):
    monkeypatch.setattr(main, "create_ledger", Mock(side_effect=AssertionError("state touched")))
    publish = Mock(return_value=None)
    monkeypatch.setattr(main, "post_carousel", publish)
    main.run(now=NOW, dry_run=True)
    assert publish.call_args.kwargs["dry_run"] is True
    assert not dedup.POSTED_TOPICS_FILE.exists()


def test_publish_timeout_remains_uncertain_and_blocks_retry(runner, monkeypatch):
    ledger, slots = runner

    def timeout(*args, before_publish, **kwargs):
        before_publish("container")
        raise TimeoutError("response lost")

    monkeypatch.setattr(main, "post_carousel", timeout)
    with pytest.raises(RuntimeError):
        main.run(now=NOW)
    key = f"2026-09-20|10:00|{slots[0].pillar['id']}"
    assert ledger.get(key)["status"] == "uncertain"
    with pytest.raises(RuntimeError, match="reconcil"):
        main.run(now=NOW + timedelta(hours=4))


def test_preview_works_even_on_a_day_without_scheduled_posts(runner, monkeypatch):
    _, slots = runner
    slots.clear()
    publish = Mock(return_value=None)
    monkeypatch.setattr(main, "post_carousel", publish)
    result = main.run(now=NOW, dry_run=True)
    assert result["status"] == "preview"
    publish.assert_called_once()


def test_no_publication_outside_the_window(runner, monkeypatch):
    publish = Mock()
    monkeypatch.setattr(main, "post_carousel", publish)
    assert main.run(now=NOW.replace(hour=21))["status"] == "skipped"
    publish.assert_not_called()


def test_cli_failure_exits_nonzero_without_printing_nested_credentials(monkeypatch, caplog):
    monkeypatch.setattr(main.sys, "argv", ["instagram"])
    monkeypatch.setattr(main, "run", Mock(side_effect=RuntimeError("publication failed")))
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 1
    assert "publication failed" in caplog.text


def test_cli_dry_run_cannot_reconcile_state(monkeypatch):
    monkeypatch.setattr(
        main.sys, "argv", ["instagram", "--dry-run", "--resolve-slot", "slot", "--media-id", "id"]
    )
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 2
