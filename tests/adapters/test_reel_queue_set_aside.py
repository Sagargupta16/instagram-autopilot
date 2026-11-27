"""Tests for setting a queued pair aside: judged only on whole bytes, renamed by id under a
minute stamp, never deleted, and counted from every page of assets (contract 32)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from requests.exceptions import HTTPError

from src.adapters import reel_queue
from src.adapters.reel_queue import BadPair, QueueError, ReelQueue
from tests.fake_release import Release, entry, video

NOW = datetime(2026, 11, 27, 4, 32, 59, tzinfo=UTC)
OTIS = "otis-cut-the-rope"


@pytest.fixture
def release(monkeypatch) -> Release:
    fake = Release()
    monkeypatch.setattr(reel_queue, "requests", fake)
    return fake


@pytest.fixture
def queue() -> ReelQueue:
    return ReelQueue("owner/repo", "token")


def test_both_assets_take_the_minute_stamp_of_the_passed_clock(release, queue) -> None:
    meta, mp4 = release.pair(OTIS, entry("Otis cut the rope"))
    india = NOW.astimezone(timezone(timedelta(hours=5, minutes=30)))

    suffix = queue.set_aside(BadPair(OTIS, mp4, meta, "30 fps"), india)

    assert suffix == ".failed-20261127T0432Z"
    assert release.renames == [(mp4, f"{OTIS}.mp4{suffix}"), (meta, f"{OTIS}.json{suffix}")]
    assert len(release.assets) == 2  # renamed, never deleted


def test_a_taken_name_moves_both_assets_to_the_next_free_suffix(release, queue) -> None:
    release.add(f"{OTIS}.json.failed-20261127T0432Z")
    release.add(f"{OTIS}.mp4.failed-20261127T0432Z-2")
    meta, mp4 = release.pair(OTIS, entry("Otis cut the rope"))

    suffix = queue.set_aside(BadPair(OTIS, mp4, meta, "30 fps"), NOW)

    assert suffix == ".failed-20261127T0432Z-3"
    assert release.name(mp4) == f"{OTIS}.mp4.failed-20261127T0432Z-3"
    assert release.name(meta) == f"{OTIS}.json.failed-20261127T0432Z-3"


def test_the_judged_ids_are_renamed_not_whatever_holds_the_name_now(release, queue) -> None:
    judged_meta, judged_mp4 = release.pair(OTIS, entry("Otis cut the rope"))
    release.assets[judged_meta]["name"] = "renamed-by-hand.json"
    mended = release.add(f"{OTIS}.json", b"{}")

    queue.set_aside(BadPair(OTIS, judged_mp4, judged_meta, "30 fps"), NOW)

    assert [number for number, _ in release.renames] == [judged_mp4, judged_meta]
    assert release.name(mended) == f"{OTIS}.json"


def test_set_aside_pairs_are_counted_once_from_the_stamp_on(release, queue) -> None:
    for name in ("a", "b"):
        release.add(f"{name}.mp4.failed-20261126T1500Z")
        release.add(f"{name}.json.failed-20261126T1500Z")
    release.add("c.mp4.failed-20261126T1459Z")  # half renamed, before the moment
    release.add("d.json.failed-20261127T0100Z-2")  # half renamed, after it
    release.add("posted-e.mp4")

    since = datetime(2026, 11, 26, 15, 0, 30, tzinfo=UTC)
    assert queue.set_aside_since(since) == 3
    assert queue.set_aside_since(None) == 4


def test_set_aside_names_past_the_first_hundred_assets_count(release, queue) -> None:
    for number in range(50):
        release.add(f"aaa-{number:02d}.mp4")
        release.add(f"aaa-{number:02d}.json")
    release.add("zz.mp4.failed-20261127T0100Z")

    assert queue.set_aside_since(None) == 1


def test_a_whole_json_that_does_not_validate_is_a_bad_pair(release, queue) -> None:
    meta, mp4 = release.pair(OTIS, entry("Otis cut the rope", duration_s=9))

    with pytest.raises(BadPair) as bad:
        queue.next_item(published=set())

    assert (bad.value.slug, bad.value.video_asset, bad.value.meta_asset) == (OTIS, mp4, meta)
    assert bad.value.reason.startswith("its JSON does not validate: duration_s")
    assert "Otis" not in bad.value.reason  # the entry's own text stays out of public summaries


def test_a_json_whose_size_is_not_listed_is_never_judged(release, queue) -> None:
    release.add(f"{OTIS}.json", b"not json", listed=False)
    release.add(f"{OTIS}.mp4", video())

    with pytest.raises(QueueError, match="is malformed") as error:
        queue.next_item(published=set())

    assert not isinstance(error.value, BadPair)


def test_a_json_that_contradicts_its_digest_is_a_download_fault(release, queue) -> None:
    meta, _ = release.pair(OTIS, b"not json")
    release.served[meta] = b"NOT JSON"

    with pytest.raises(QueueError, match="did not arrive whole") as error:
        queue.next_item(published=set())

    assert not isinstance(error.value, BadPair)


def test_a_digest_in_another_algorithm_is_not_read(release, queue) -> None:
    meta, _ = release.pair(OTIS, entry("Otis cut the rope"))
    release.assets[meta]["digest"] = "sha512:abc"

    item = queue.next_item(published=set())

    assert item is not None and item.slug == OTIS


def test_excluded_slugs_are_passed_over(release, queue) -> None:
    release.pair(OTIS, entry("Otis cut the rope"))
    release.pair("orcas", entry("Orcas sink yachts"))

    item = queue.next_item(published=set(), exclude=frozenset({OTIS}))

    assert item is not None and item.slug == "orcas"


def test_a_short_video_download_raises_before_it_is_saved(release, queue, tmp_path) -> None:
    release.pair(OTIS, entry("Otis cut the rope"))
    item = queue.next_item(published=set())
    release.served[item.video_asset] = video()[:-4]
    path = tmp_path / "reel.mp4"

    with pytest.raises(QueueError, match="did not arrive whole"):
        queue.video(item, path)

    assert not path.exists()


def test_a_second_rename_that_fails_gives_the_video_its_name_back(
    release, queue, monkeypatch
) -> None:
    meta, mp4 = release.pair(OTIS, entry("Otis cut the rope"))
    patch = release.patch

    def failing(url: str, **kwargs):
        if kwargs["json"]["name"].startswith(f"{OTIS}.json"):
            raise HTTPError("502 Bad Gateway")
        return patch(url, **kwargs)

    monkeypatch.setattr(release, "patch", failing)

    with pytest.raises(HTTPError):
        queue.set_aside(BadPair(OTIS, mp4, meta, "30 fps"), NOW)

    assert release.names() == [f"{OTIS}.json", f"{OTIS}.mp4"]  # whole again: nothing half aside


def test_a_pair_left_half_aside_says_which_asset_carries_which_name(
    release, queue, monkeypatch
) -> None:
    meta, mp4 = release.pair(OTIS, entry("Otis cut the rope"))
    patch, asked = release.patch, []

    def failing(url: str, **kwargs):
        asked.append(kwargs["json"]["name"])
        if len(asked) > 1:  # the first rename works, the second and the way back do not
            raise HTTPError("502 Bad Gateway")
        return patch(url, **kwargs)

    monkeypatch.setattr(release, "patch", failing)

    with pytest.raises(QueueError, match="may be half set aside"):
        queue.set_aside(BadPair(OTIS, mp4, meta, "30 fps"), NOW)

    assert release.name(mp4) == f"{OTIS}.mp4.failed-20261127T0432Z"
    assert release.name(meta) == f"{OTIS}.json"


def test_a_rename_whose_answer_is_lost_is_undone_from_the_listing(
    release, queue, monkeypatch
) -> None:
    meta, mp4 = release.pair(OTIS, entry("Otis cut the rope"))
    patch = release.patch

    def lost(url: str, **kwargs):
        done = patch(url, **kwargs)  # the rename lands on the release ...
        if kwargs["json"]["name"].startswith(f"{OTIS}.json.failed-"):
            raise HTTPError("read timed out")  # ... and its answer never arrives
        return done

    monkeypatch.setattr(release, "patch", lost)

    with pytest.raises(HTTPError, match="read timed out"):
        queue.set_aside(BadPair(OTIS, mp4, meta, "30 fps"), NOW)

    assert release.names() == [f"{OTIS}.json", f"{OTIS}.mp4"]  # both back, found by listing


def test_a_whole_json_nested_too_deep_is_a_bad_pair(release, queue) -> None:
    release.pair(OTIS, b"[" * 100_000 + b"]" * 100_000)

    # How deep a parser goes is the interpreter's and the platform's business: Python 3.12 gives
    # up on this body, 3.14 on Linux parses it and the schema refuses the list it gets.
    with pytest.raises(BadPair, match=r"does not parse|does not validate: entry"):
        queue.next_item(published=set())


def test_a_reason_names_the_entrys_fields_and_no_key_the_entry_made_up(release, queue) -> None:
    made_up = entry("Otis cut the rope", secret_name="x", sources=[{"private-key": 1}])
    release.pair(OTIS, made_up)

    with pytest.raises(BadPair) as bad:
        queue.next_item(published=set())

    assert "secret_name" not in bad.value.reason and "private-key" not in bad.value.reason
    assert "sources: " in bad.value.reason and "entry: " in bad.value.reason
