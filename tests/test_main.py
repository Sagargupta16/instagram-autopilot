"""Exercise orchestration with real local state and mocked service boundaries."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from src import main
from src.content import dedup
from src.flows import svg_reel_flow
from src.media.reel_svg import Reel
from src.media.svg_look import LOOKS
from src.schedule import SlotPlan
from src.slot_rules import next_look
from src.state.ledger import Ledger
from src.state.local import LocalStore

NOW = datetime(2026, 9, 20, 12, tzinfo=UTC)


@pytest.fixture
def runner(monkeypatch, tmp_path, sample_config, sample_caption_data):
    # The shipped pillars are SVG Reels; these orchestration tests keep the carousel path.
    carousel = {**sample_config["pillars"][0], "id": "photo-carousel", "content_format": "carousel"}
    carousel.pop("scene_kind", None)
    sample_config["pillars"].insert(0, carousel)
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


def pillar(config, pillar_id):
    return next(item for item in config["pillars"] if item["id"] == pillar_id)


def publishing(media_id="media"):
    def publish(*args, before_publish, **kwargs):
        before_publish("container")
        return media_id

    return Mock(side_effect=publish)


@pytest.fixture
def flows(monkeypatch):
    svg, carousel = publishing("svg-media"), publishing("carousel-media")
    monkeypatch.setattr(main, "post_svg_reel", svg)
    monkeypatch.setattr(main, "post_carousel", carousel)
    return svg, carousel


def test_svg_reel_slot_dispatches_with_the_pillar_audio_theme(
    runner, flows, sample_config, sample_caption_data
):
    _, slots = runner
    svg, carousel = flows
    tech = pillar(sample_config, "tech-explainer")
    slots[:] = [SlotPlan("10:00", tech, False)]
    assert main.run(now=NOW)["media_id"] == "svg-media"
    args, kwargs = svg.call_args
    caption = sample_caption_data["caption"] + "\n\n" + sample_caption_data["hashtags"]
    assert args == (sample_caption_data, caption)
    assert set(kwargs) == {"audio_theme", "dry_run", "before_publish"}
    assert kwargs["audio_theme"] == tech["audio_theme"]
    assert kwargs["dry_run"] is False
    carousel.assert_not_called()


@pytest.mark.parametrize("planned", [True, False])
def test_forced_pillar_preview_replaces_the_planned_pillar(runner, flows, sample_config, planned):
    _, slots = runner
    svg, carousel = flows
    svg.side_effect, svg.return_value = None, None
    if not planned:
        slots.clear()
    result = main.run(dry_run=True, now=NOW, pillar_id="cool-stats")
    assert result["status"] == "preview"
    assert result["slot"] == f"2026-09-20|{'10:00' if planned else '12:00'}|cool-stats"
    assert main.generate_topic_brief.call_args.args[0]["id"] == "cool-stats"
    assert svg.call_args.kwargs["audio_theme"] == pillar(sample_config, "cool-stats")["audio_theme"]
    carousel.assert_not_called()


@pytest.mark.parametrize("dry_run", [True, False])
def test_unknown_pillar_fails_before_generation(runner, dry_run):
    with pytest.raises(ValueError, match="Unknown pillar 'nope'"):
        main.run(dry_run=dry_run, now=NOW, pillar_id="nope")
    main.generate_topic_brief.assert_not_called()
    main._preflight_all_auth.assert_not_called()


def test_forced_pillar_waits_for_a_due_slot(runner, flows):
    _, slots = runner
    slots[:] = [SlotPlan("18:00", slots[0].pillar, False)]
    assert main.run(now=NOW, pillar_id="cool-stats")["status"] == "skipped"
    flows[0].assert_not_called()
    main._preflight_all_auth.assert_not_called()


def test_forced_pillar_keeps_the_minimum_gap(runner, flows, sample_config):
    _, slots = runner
    svg, _ = flows
    slots.append(SlotPlan("12:10", slots[0].pillar, False))
    assert main.run(now=NOW)["status"] == "published"
    assert main.run(now=NOW + timedelta(minutes=20), pillar_id="cool-stats")["status"] == "skipped"
    svg.assert_not_called()
    later = NOW + timedelta(minutes=sample_config["cadence"]["min_gap_minutes"] + 1)
    assert main.run(now=later, pillar_id="cool-stats")["slot"] == "2026-09-20|12:10|cool-stats"
    svg.assert_called_once()


def test_forced_pillar_keeps_the_daily_cap(runner, flows, sample_config):
    _, slots = runner
    sample_config["cadence"]["max_posts_per_day"] = 1
    slots.append(SlotPlan("12:10", slots[0].pillar, False))
    assert main.run(now=NOW)["status"] == "published"
    assert main.run(now=NOW + timedelta(hours=2), pillar_id="cool-stats")["status"] == "skipped"
    flows[0].assert_not_called()


def test_planned_pillar_skips_a_slot_time_a_forced_pillar_filled(runner, flows):
    ledger, _ = runner
    assert main.run(now=NOW, pillar_id="cool-stats")["slot"] == "2026-09-20|10:00|cool-stats"
    assert main.run(now=NOW + timedelta(hours=2))["status"] == "skipped"
    flows[1].assert_not_called()
    assert ledger.get("2026-09-20|10:00|photo-carousel") == {}


def test_post_now_publishes_once_at_the_current_minute(runner, flows):
    ledger, _ = runner
    svg, carousel = flows
    result = main.run(now=NOW, pillar_id="cool-stats", post_now=True)
    key = "2026-09-20|12:00|cool-stats"
    assert result == {"status": "published", "slot": key, "media_id": "svg-media"}
    svg.assert_called_once()
    carousel.assert_not_called()
    assert ledger.get(key)["media_id"] == "svg-media"


def summary():
    return json.loads(Path("output/run-summary.json").read_text("utf-8"))


def test_post_now_is_refused_inside_the_minimum_gap(runner, flows):
    main.run(now=NOW, pillar_id="cool-stats", post_now=True)
    with pytest.raises(RuntimeError, match=r"^Post-now refused: the minimum gap"):
        main.run(now=NOW + timedelta(minutes=20), pillar_id="cool-stats", post_now=True)
    assert flows[0].call_count == 1
    assert summary()["status"] == "refused"
    assert "minimum gap" in summary()["reason"]


def test_post_now_is_refused_at_the_daily_cap(runner, flows, sample_config):
    cadence = sample_config["cadence"]
    start, spacing = NOW.replace(hour=5), timedelta(minutes=cadence["min_gap_minutes"] + 1)
    for index in range(cadence["max_posts_per_day"]):
        moment = start + index * spacing
        assert main.run(now=moment, pillar_id="cool-stats", post_now=True)["status"] == "published"
    with pytest.raises(RuntimeError, match=r"^Post-now refused: the daily cap"):
        main.run(
            now=start + cadence["max_posts_per_day"] * spacing,
            pillar_id="cool-stats",
            post_now=True,
        )
    assert flows[0].call_count == cadence["max_posts_per_day"]
    assert summary()["status"] == "refused"


def test_post_now_is_refused_outside_the_window_or_when_owned(runner, flows):
    ledger, _ = runner
    with pytest.raises(RuntimeError, match=r"^Post-now refused: outside the posting window"):
        main.run(now=NOW.replace(hour=21), pillar_id="cool-stats", post_now=True)
    assert ledger.claim("2026-09-20|11:55|tech-explainer", NOW, min_gap_minutes=60)
    with pytest.raises(RuntimeError, match=r"^Post-now refused: slot .* owned by another run"):
        main.run(now=NOW, pillar_id="cool-stats", post_now=True)
    flows[0].assert_not_called()


def test_post_now_requires_a_pillar(runner):
    with pytest.raises(ValueError, match="requires a pillar"):
        main.run(now=NOW, post_now=True)


def test_post_now_dry_run_never_builds_the_ledger_or_uploads(
    runner, monkeypatch, sample_caption_data
):
    monkeypatch.setattr(main, "create_ledger", Mock(side_effect=AssertionError("state touched")))
    sample_caption_data["scene"] = {"kind": "steps"}
    prepared = ("caption", Reel("<svg/>", 15.0, (), 11.5), b"mp4", None)
    monkeypatch.setattr(svg_reel_flow, "_prepare", Mock(return_value=prepared))
    upload, publish = Mock(), Mock()
    monkeypatch.setattr(svg_reel_flow, "upload_video", upload)
    monkeypatch.setattr(svg_reel_flow, "publish_reel", publish)
    result = main.run(dry_run=True, now=NOW, pillar_id="cool-stats", post_now=True)
    assert result == {"status": "preview", "slot": "2026-09-20|12:00|cool-stats", "media_id": None}
    upload.assert_not_called()
    publish.assert_not_called()
    assert [path.name for path in Path("output/dry-run").rglob("01.mp4")] == ["01.mp4"]


@pytest.mark.parametrize("post_now", [False, True])
def test_cli_passes_the_pillar_and_post_now_to_run(monkeypatch, post_now):
    argv = ["instagram", "--pillar", "cool-stats", *(["--post-now"] if post_now else [])]
    monkeypatch.setattr(main.sys, "argv", argv)
    run = Mock()
    monkeypatch.setattr(main, "run", run)
    main.main()
    run.assert_called_once_with(dry_run=False, pillar_id="cool-stats", post_now=post_now)


@pytest.mark.parametrize(
    "argv",
    [
        ["--pillar", "cool-stats", "--resolve-slot", "slot", "--media-id", "id"],
        ["--pillar", "cool-stats", "--post-now", "--resolve-slot", "slot", "--media-id", "id"],
        ["--post-now"],
        ["--post-now", "--dry-run"],
    ],
)
def test_cli_rejects_invalid_pillar_combinations(monkeypatch, argv):
    monkeypatch.setattr(main.sys, "argv", ["instagram", *argv])
    monkeypatch.setattr(main, "run", Mock(side_effect=AssertionError("ran")))
    monkeypatch.setattr(main, "create_ledger", Mock(side_effect=AssertionError("state touched")))
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 2


def test_each_post_takes_the_look_after_the_last_published_one(runner, flows, sample_config):
    ledger, slots = runner
    svg, _ = flows
    tech = pillar(sample_config, "tech-explainer")
    slots[:] = [SlotPlan("10:00", tech, False), SlotPlan("14:00", tech, False)]
    main.generate_caption.return_value = {
        **main.generate_caption.return_value,
        "scene": {"kind": "steps"},
    }
    first = NOW.replace(hour=10, minute=5)
    main.run(now=first)
    look = svg.call_args.args[0]["look"]
    assert look == first.date().toordinal() % len(LOOKS)
    assert ledger.get("2026-09-20|10:00|tech-explainer")["look"] == look
    main.run(now=NOW.replace(hour=14, minute=5))
    assert svg.call_args.args[0]["look"] == (look + 1) % len(LOOKS)
    assert ledger.get("2026-09-20|14:00|tech-explainer")["look"] == (look + 1) % len(LOOKS)


def test_next_look_rotates_past_the_latest_published_receipt():
    day = NOW.date()
    assert next_look({}, 3, day) == day.toordinal() % 3
    slots = {
        "a": {"status": "published", "published_at": "2026-09-19T10:00:00+00:00", "look": 2},
        "b": {"status": "published", "published_at": "2026-09-20T09:00:00+00:00", "look": 0},
        "c": {"status": "failed", "look": 1},
        "d": {"status": "published", "published_at": "2026-09-20T11:00:00+00:00"},
    }
    assert next_look(slots, 3, day) == 1
    slots["b"]["look"] = 2
    assert next_look(slots, 3, day) == 0
