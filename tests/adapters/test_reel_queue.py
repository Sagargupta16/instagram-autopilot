"""Tests for the Reel queue adapter: the draft release is read to its last page of assets."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.adapters.reel_queue import ReelQueue

ENTRY = {
    "title": "Wojtek, the soldier bear",
    "pillar": "history-timeline",
    "caption": "A bear that carried shells.",
    "duration_s": 60.0,
    "audio": True,
}


def asset(number: int, name: str) -> dict[str, Any]:
    return {"id": number, "name": name, "created_at": f"2026-11-01T00:{number % 60:02d}:00Z"}


def posted(count: int) -> list[dict[str, Any]]:
    """`count` assets of pairs that have posted, as GitHub lists them: by name."""
    return [
        asset(number, f"posted-video-{number // 2:03d}.{'json' if number % 2 else 'mp4'}")
        for number in range(count)
    ]


def queue_of(
    pages: list[list[dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> tuple[ReelQueue, list[int]]:
    """A queue whose release lists its assets in `pages`, and the asset pages that were asked for."""
    queue = ReelQueue("owner/repo", "token")
    asked: list[int] = []

    def get(path: str, **kwargs: Any) -> MagicMock:
        response = MagicMock()
        if path == "/releases":
            response.json.return_value = [{"id": 7, "draft": True, "tag_name": "reel-queue"}]
        elif path == "/releases/7/assets":
            page = kwargs["params"].get("page", 1)
            asked.append(page)
            response.json.return_value = pages[page - 1] if page <= len(pages) else []
        else:
            response.content = json.dumps(ENTRY).encode()
        return response

    monkeypatch.setattr(queue, "_get", get)
    return queue, asked


def test_a_pair_past_the_first_hundred_assets_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    # 100 kept assets of posted pairs fill the first page; a waiting pair whose name sorts after
    # them is on the second (wojtek, sahara, sunlight and telegraphs on 2026-11-26)
    waiting = [asset(900, "wojtek-soldier-bear.json"), asset(901, "wojtek-soldier-bear.mp4")]
    queue, asked = queue_of([posted(100), waiting], monkeypatch)

    item = queue.next_item(published=set())

    assert item is not None
    assert (item.slug, item.meta_asset, item.video_asset) == ("wojtek-soldier-bear", 900, 901)
    assert asked == [1, 2]


def test_a_named_pair_past_the_first_hundred_assets_is_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waiting = [asset(900, "wojtek-soldier-bear.json"), asset(901, "wojtek-soldier-bear.mp4")]
    queue, _ = queue_of([posted(100), waiting], monkeypatch)

    item = queue.next_item(published=set(), slug="wojtek-soldier-bear")

    assert item is not None and item.slug == "wojtek-soldier-bear"


def test_a_full_last_page_asks_for_one_more(monkeypatch: pytest.MonkeyPatch) -> None:
    queue, asked = queue_of([posted(100)], monkeypatch)

    assert queue.next_item(published=set()) is None
    assert asked == [1, 2]


def test_a_short_first_page_is_one_request(monkeypatch: pytest.MonkeyPatch) -> None:
    waiting = [asset(1, "lake-baikal.json"), asset(2, "lake-baikal.mp4")]
    queue, asked = queue_of([posted(10) + waiting], monkeypatch)

    item = queue.next_item(published=set())

    assert item is not None and item.slug == "lake-baikal"
    assert asked == [1]
