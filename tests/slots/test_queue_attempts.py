"""A queue run sets aside a pair that is bad in its own files and posts the next one, and sets
nothing aside for a failure that is not in the pair (contract 32). These runs execute the real
adapter, flow, checkpoint and ledger; only GitHub, ffprobe, Cloudinary, Composio and the publish
call are faked."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from src import main
from src.adapters import cloudinary_host, composio, reel_queue
from src.content import dedup
from src.flows import queued_reel_flow
from src.media.video import reel_probe
from src.slots import queued_post, slot_rules
from src.slots.schedule import SlotPlan
from src.state.ledger import Ledger
from src.state.local import LocalStore
from tests.fake_release import BAD_FPS, GOOD, Release, entry, video

NOW = datetime(2026, 11, 27, 4, 32, 40, tzinfo=UTC)
DAY = "2026-11-27|04:10"
KEY = f"{DAY}|history-timeline"
AS = ".failed-20261127T0432Z"
OTIS, ORCAS = "otis-cut-the-rope", "orcas-sink-yachts"


@pytest.fixture
def release(monkeypatch, tmp_path, sample_config) -> Release:
    fake = Release()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reel_queue, "requests", fake)
    monkeypatch.setattr(reel_probe.subprocess, "run", fake.run)
    monkeypatch.setattr(
        reel_queue.ReelQueue, "from_settings", classmethod(lambda cls: cls("owner/repo", "token"))
    )
    sample_config["video_source"] = "queue"
    monkeypatch.setattr(main, "load_config", lambda: sample_config)
    slots = [SlotPlan("04:10", sample_config["pillars"][0], False)]
    monkeypatch.setattr(slot_rules, "plan_today", lambda *args: slots)
    monkeypatch.setattr(dedup, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dedup, "POSTED_TOPICS_FILE", tmp_path / "topics.json")
    for module, name in ((cloudinary_host, "configure"), (cloudinary_host, "verify_auth")):
        monkeypatch.setattr(module, name, Mock())
    monkeypatch.setattr(composio, "verify_auth", Mock())
    monkeypatch.setattr(queued_reel_flow, "upload_video", Mock(return_value="https://cdn/r.mp4"))
    return fake


@pytest.fixture
def ledger(monkeypatch, tmp_path) -> Ledger:
    store = Ledger(LocalStore(tmp_path / "publication.json"))
    monkeypatch.setattr(main, "create_ledger", lambda: store)
    return store


@pytest.fixture
def publish(monkeypatch) -> Mock:
    def published(*, video_url, caption, before_publish, thumb_offset):
        before_publish("container-1")
        return "media-1"

    fake = Mock(side_effect=published)
    monkeypatch.setattr(queued_reel_flow, "publish_reel", fake)
    return fake


def summary() -> dict:
    return json.loads(Path("output/run-summary.json").read_text("utf-8"))


def seed_published(ledger: Ledger, when: datetime) -> None:
    key = f"{when.date().isoformat()}|{when.strftime('%H:%M')}|cool-stats"
    assert ledger.claim(key, when, min_gap_minutes=180)
    ledger.before_publish(key, "container-0", when)
    ledger.complete(key, "media-0", when)


def seed_set_aside(release: Release, *stamps: str) -> None:
    for number, stamp in enumerate(stamps):
        release.add(f"old-{number}.json.failed-{stamp}")
        release.add(f"old-{number}.mp4.failed-{stamp}")


def test_a_bad_video_is_set_aside_and_the_next_pair_posts_in_the_same_run(
    release, ledger, publish
) -> None:
    otis = release.pair(OTIS, entry("Otis cut the rope"), video(BAD_FPS))
    orcas = release.pair(ORCAS, entry("Orcas sink yachts", pillar="cool-stats"))

    result = main.run(now=NOW)

    following = f"{DAY}|cool-stats"
    assert (result["status"], result["slot"], result["queued"]) == ("published", following, ORCAS)
    receipt = ledger.get(following)
    assert (receipt["status"], receipt["topic"], receipt["media_id"]) == (
        "published",
        "Orcas sink yachts",
        "media-1",
    )
    assert ledger.get(KEY)["status"] == "failed"
    assert publish.call_args.kwargs["caption"].startswith("Orcas sink yachts")
    assert release.renames == [
        (otis[1], f"{OTIS}.mp4{AS}"),
        (otis[0], f"{OTIS}.json{AS}"),
        (orcas[1], f"posted-{ORCAS}.mp4"),
        (orcas[0], f"posted-{ORCAS}.json"),
    ]
    (aside,) = summary()["set_aside"]
    assert (aside["slug"], aside["as"]) == (OTIS, AS)
    assert "30 fps" in aside["reason"]


def test_a_short_video_download_is_not_judged_and_nothing_is_renamed(
    release, ledger, publish
) -> None:
    otis = release.pair(OTIS, entry("Otis cut the rope"))
    release.pair(ORCAS, entry("Orcas sink yachts"))
    release.served[otis[1]] = release.assets[otis[1]]["body"][:-8]  # the download was cut short

    with pytest.raises(RuntimeError, match=f"Publication failed for {KEY}") as error:
        main.run(now=NOW)

    assert release.probed == []  # ffprobe never judged the cut bytes
    assert "did not arrive whole" in str(error.value.__cause__)
    assert release.renames == []
    assert ledger.get(KEY)["status"] == "failed"
    publish.assert_not_called()
    assert "set_aside" not in summary()


def _cut(release, otis):
    release.served[otis[1]] = release.assets[otis[1]]["body"][:-8]


def _swapped(release, otis):
    release.served[otis[1]] = release.assets[otis[1]]["body"].replace(b"x", b"y")


def _ffprobe(mode):
    def fault(release, otis):
        release.ffprobe = mode

    return fault


def _upload_error(release, otis):
    queued_reel_flow.upload_video.side_effect = RuntimeError("Cloudinary rejected the upload")


def _auth_error(release, otis):
    composio.verify_auth.side_effect = RuntimeError("Composio connection EXPIRED")


@pytest.mark.parametrize(
    ("fault", "mp4"),
    [
        (_cut, BAD_FPS),  # cut bytes are never judged, even ones that would fail the check
        (_swapped, BAD_FPS),
        (_ffprobe("missing"), BAD_FPS),
        (_ffprobe("timeout"), BAD_FPS),
        (_ffprobe("killed"), BAD_FPS),
        (_ffprobe("broken"), GOOD),  # an install that exits 1 on every file
        (_upload_error, GOOD),
        (_auth_error, BAD_FPS),
    ],
    ids=[
        "short-mp4",
        "digest",
        "ffprobe-missing",
        "ffprobe-timeout",
        "ffprobe-killed",
        "ffprobe-broken",
        "upload",
        "auth",
    ],
)
def test_a_failure_outside_the_pair_sets_nothing_aside(
    release, ledger, publish, fault, mp4
) -> None:
    otis = release.pair(OTIS, entry("Otis cut the rope"), video(mp4))
    release.pair(ORCAS, entry("Orcas sink yachts"))
    fault(release, otis)

    with pytest.raises(RuntimeError, match=f"Publication failed for {KEY}"):
        main.run(now=NOW)

    assert release.renames == []
    assert ledger.get(KEY)["status"] == "failed"
    publish.assert_not_called()
    assert summary()["status"] == "failed"
    assert "set_aside" not in summary()


def test_a_publish_error_sets_nothing_aside_and_stays_uncertain(release, ledger, monkeypatch):
    def lost(*, before_publish, **kwargs):
        before_publish("container-1")
        raise TimeoutError("publish response lost")

    publish = Mock(side_effect=lost)
    monkeypatch.setattr(queued_reel_flow, "publish_reel", publish)
    release.pair(OTIS, entry("Otis cut the rope"))
    release.pair(ORCAS, entry("Orcas sink yachts"))

    with pytest.raises(RuntimeError, match=f"Publication failed for {KEY}"):
        main.run(now=NOW)

    assert release.renames == []
    assert ledger.get(KEY)["status"] == "uncertain"
    publish.assert_called_once()


def test_a_short_json_download_fails_the_run_before_any_claim(release, ledger, publish) -> None:
    otis = release.pair(OTIS, entry("Otis cut the rope"))
    release.pair(ORCAS, entry("Orcas sink yachts"))
    release.served[otis[0]] = release.assets[otis[0]]["body"][:-5]

    with pytest.raises(reel_queue.QueueError, match="did not arrive whole"):
        main.run(now=NOW)

    assert release.renames == []
    assert ledger.snapshot()["slots"] == {}
    publish.assert_not_called()


def test_a_malformed_json_at_the_head_is_set_aside_before_any_claim(
    release, ledger, publish
) -> None:
    otis = release.pair(OTIS, b'{"title": "Otis cut the rope", "pillar": ')
    release.pair(ORCAS, entry("Orcas sink yachts"))

    result = main.run(now=NOW)

    assert (result["status"], result["queued"]) == ("published", ORCAS)
    assert list(ledger.snapshot()["slots"]) == [KEY]
    assert ledger.get(KEY)["attempts"] == 1
    assert release.renames[:2] == [(otis[1], f"{OTIS}.mp4{AS}"), (otis[0], f"{OTIS}.json{AS}")]
    assert summary()["set_aside"] == [{"slug": OTIS, "reason": "its JSON does not parse", "as": AS}]


def test_an_invalid_entry_is_set_aside_and_an_empty_queue_then_skips(release, ledger) -> None:
    release.pair(OTIS, entry("Otis cut the rope", hashtags="#a #b #c #d #e #f"))

    result = main.run(now=NOW)

    assert result["status"] == "skipped"
    (aside,) = summary()["set_aside"]
    assert aside["slug"] == OTIS
    assert "more than 5 hashtags" in aside["reason"]
    assert ledger.snapshot()["slots"] == {}


def test_a_receipt_not_back_at_failed_stops_the_move_on(
    release, ledger, publish, monkeypatch
) -> None:
    otis = release.pair(OTIS, entry("Otis cut the rope"))
    release.pair(ORCAS, entry("Orcas sink yachts"))

    def past_the_checkpoint(item, queue, *, dry_run, before_publish):
        before_publish("container-1")
        raise reel_queue.BadPair(item.slug, otis[1], otis[0], "judged too late")

    monkeypatch.setattr(queued_post, "post_queued_reel", past_the_checkpoint)

    with pytest.raises(RuntimeError, match=f"Publication failed for {KEY}"):
        main.run(now=NOW)

    assert ledger.get(KEY)["status"] == "uncertain"
    assert release.renames == []
    publish.assert_not_called()


def test_three_pairs_set_aside_since_the_last_post_stop_a_fourth(release, ledger, publish) -> None:
    seed_published(ledger, datetime(2026, 11, 26, 15, 0, tzinfo=UTC))
    seed_set_aside(release, "20261126T1600Z", "20261126T1700Z", "20261127T0100Z")
    release.pair(OTIS, entry("Otis cut the rope"), video(BAD_FPS))
    release.pair(ORCAS, entry("Orcas sink yachts"))

    with pytest.raises(RuntimeError, match=f"Publication failed for {KEY}") as error:
        main.run(now=NOW)

    assert "3 pairs were already set aside" in str(error.value.__cause__)
    assert release.renames == []
    assert ledger.get(KEY)["status"] == "failed"
    publish.assert_not_called()


def test_pairs_set_aside_before_the_last_post_do_not_count(release, ledger, publish) -> None:
    seed_published(ledger, datetime(2026, 11, 26, 15, 0, tzinfo=UTC))
    seed_set_aside(release, "20261125T1600Z", "20261126T0900Z", "20261126T1459Z")
    release.pair(OTIS, entry("Otis cut the rope"), video(BAD_FPS))
    release.pair(ORCAS, entry("Orcas sink yachts"))

    assert main.run(now=NOW)["queued"] == ORCAS
    assert summary()["set_aside"][0]["slug"] == OTIS


def test_with_no_published_receipt_every_set_aside_pair_counts(release, ledger, publish) -> None:
    seed_set_aside(release, "20261001T1600Z", "20261002T0900Z", "20261003T1459Z")
    release.pair(OTIS, entry("Otis cut the rope"), video(BAD_FPS))
    release.pair(ORCAS, entry("Orcas sink yachts"))

    with pytest.raises(RuntimeError, match=f"Publication failed for {KEY}"):
        main.run(now=NOW)

    assert release.renames == []
    publish.assert_not_called()


def test_post_now_with_a_slug_sets_a_bad_pair_aside_and_refuses(release, ledger, publish):
    release.pair(ORCAS, entry("Orcas sink yachts"))
    otis = release.pair(OTIS, entry("Otis cut the rope"), video(BAD_FPS))

    with pytest.raises(
        RuntimeError, match=rf"^Post-now refused: queued video {OTIS} was set aside"
    ):
        main.run(now=NOW, pillar_id="tech-explainer", post_now=True, slug=OTIS)

    assert release.renames == [(otis[1], f"{OTIS}.mp4{AS}"), (otis[0], f"{OTIS}.json{AS}")]
    publish.assert_not_called()
    assert summary()["status"] == "refused"
    assert summary()["set_aside"][0]["slug"] == OTIS
    assert ledger.get("2026-11-27|04:32|history-timeline")["status"] == "failed"


def test_post_now_with_a_slug_refuses_for_a_bad_json_too(release, ledger, publish) -> None:
    release.pair(ORCAS, entry("Orcas sink yachts"))
    release.pair(OTIS, b"not json")

    with pytest.raises(
        RuntimeError, match=rf"^Post-now refused: queued video {OTIS} was set aside"
    ):
        main.run(now=NOW, pillar_id="tech-explainer", post_now=True, slug=OTIS)

    publish.assert_not_called()
    assert ledger.snapshot()["slots"] == {}


def test_post_now_without_a_slug_moves_on(release, ledger, publish) -> None:
    release.pair(OTIS, entry("Otis cut the rope"), video(BAD_FPS))
    release.pair(ORCAS, entry("Orcas sink yachts"))

    result = main.run(now=NOW, pillar_id="tech-explainer", post_now=True)

    assert (result["status"], result["queued"]) == ("published", ORCAS)
    assert ledger.get("2026-11-27|04:32|history-timeline")["topic"] == "Orcas sink yachts"


def test_a_dry_run_renames_nothing_and_never_moves_on(release, monkeypatch, publish) -> None:
    monkeypatch.setattr(main, "create_ledger", Mock(side_effect=AssertionError("state touched")))
    release.pair(OTIS, entry("Otis cut the rope"), video(BAD_FPS))
    release.pair(ORCAS, entry("Orcas sink yachts"))

    with pytest.raises(RuntimeError, match="failed"):
        main.run(dry_run=True, now=NOW)

    assert release.renames == []
    assert not Path("output/dry-run").exists()
    assert summary()["status"] == "failed"


def test_a_dry_run_with_a_bad_json_renames_nothing(release, publish) -> None:
    release.pair(OTIS, b"not json")
    release.pair(ORCAS, entry("Orcas sink yachts"))

    with pytest.raises(reel_queue.QueueError, match=OTIS):
        main.run(dry_run=True, now=NOW)

    assert release.renames == []


def test_the_next_pair_of_the_same_pillar_claims_the_same_key_again(
    release, ledger, publish
) -> None:
    release.pair(OTIS, entry("Otis cut the rope"), video(BAD_FPS))
    release.pair(ORCAS, entry("Orcas sink yachts"))

    assert main.run(now=NOW)["slot"] == KEY

    receipt = ledger.get(KEY)
    assert (receipt["status"], receipt["attempts"], receipt["topic"]) == (
        "published",
        2,
        "Orcas sink yachts",
    )


def test_the_attempt_budget_stops_the_move_on(release, ledger, publish) -> None:
    for minute in (0, 1):  # two earlier attempts on this key failed
        earlier = NOW.replace(hour=4, minute=10 + minute)
        assert ledger.claim(KEY, earlier, min_gap_minutes=180)
        ledger.fail(KEY, "Earlier", earlier)
    release.pair(OTIS, entry("Otis cut the rope"), video(BAD_FPS))
    orcas = release.pair(ORCAS, entry("Orcas sink yachts"))

    with pytest.raises(RuntimeError, match=f"Publication failed for {KEY}"):
        main.run(now=NOW)

    assert ledger.get(KEY)["attempts"] == 3
    assert summary()["slot"] == KEY
    assert release.name(orcas[1]) == f"{ORCAS}.mp4"
    publish.assert_not_called()


def test_when_the_pairs_run_out_after_a_set_aside_the_run_fails_on_the_last_key(
    release, ledger, publish
) -> None:
    release.pair(ORCAS, entry("Orcas sink yachts", pillar="cool-stats"), video(BAD_FPS))
    release.pair(OTIS, entry("Otis cut the rope"), video(BAD_FPS))

    with pytest.raises(RuntimeError, match=f"Publication failed for {KEY}"):
        main.run(now=NOW)

    outcome = summary()
    assert (outcome["status"], outcome["slot"], outcome["error"]) == ("failed", KEY, "Failed")
    assert [aside["slug"] for aside in outcome["set_aside"]] == [ORCAS, OTIS]
    assert ledger.get(f"{DAY}|cool-stats")["status"] == "failed"
    assert ledger.get(KEY)["status"] == "failed"
    publish.assert_not_called()


def test_a_video_whose_size_is_not_listed_is_never_set_aside(release, ledger, publish) -> None:
    release.add(f"{OTIS}.json", json.dumps(entry("Otis cut the rope")).encode())
    release.add(f"{OTIS}.mp4", video(BAD_FPS), listed=False)
    release.pair(ORCAS, entry("Orcas sink yachts"))

    with pytest.raises(RuntimeError, match=f"Publication failed for {KEY}"):
        main.run(now=NOW)

    assert release.renames == []
    publish.assert_not_called()


def test_a_failure_after_a_json_set_aside_still_writes_the_set_aside_summary(
    release, ledger, publish
) -> None:
    release.pair(OTIS, b"not json")
    orcas = release.pair(ORCAS, entry("Orcas sink yachts"))
    release.served[orcas[0]] = b"{}"  # the next entry arrives cut short

    with pytest.raises(reel_queue.QueueError, match="did not arrive whole"):
        main.run(now=NOW)

    outcome = summary()
    assert (outcome["status"], outcome["error"]) == ("failed", "QueueError")
    assert outcome["set_aside"][0]["slug"] == OTIS


def test_post_now_refuses_when_a_set_aside_empties_the_queue(release, ledger, publish) -> None:
    release.pair(OTIS, b"not json")

    with pytest.raises(RuntimeError, match=r"^Post-now refused: the Reel queue is empty"):
        main.run(now=NOW, pillar_id="tech-explainer", post_now=True)

    assert summary()["set_aside"][0]["slug"] == OTIS
    assert ledger.snapshot()["slots"] == {}
