"""Readiness must be established through the documented status action."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.adapters.composio import ComposioActionError, ComposioResponseError
from src.publishing.carousel import publish_carousel
from src.publishing.image_post import publish_image_post
from src.publishing.reel import publish_reel


@pytest.mark.parametrize("publisher", [publish_carousel, publish_image_post, publish_reel])
def test_waits_for_each_container_before_using_it(monkeypatch, publisher):
    events = []
    checks = {}
    ready = set()

    def post(url, *, json, **kwargs):
        slug = url.rsplit("/", 1)[-1]
        params = json["arguments"]
        events.append(slug)
        if slug == "INSTAGRAM_GET_POST_STATUS":
            assert set(params) == {"creation_id"}
            identifier = params["creation_id"]
            checks[identifier] = checks.get(identifier, 0) + 1
            if checks[identifier] == 2:
                ready.add(identifier)
            data = {"status_code": "FINISHED" if identifier in ready else "IN_PROGRESS"}
        elif slug == "INSTAGRAM_CREATE_POST":
            assert params["creation_id"] in ready
            data = {"id": "published"}
        else:
            if slug == "INSTAGRAM_CREATE_CAROUSEL_CONTAINER":
                assert set(params["children"]) <= ready
            data = {"id": f"container-{len(events)}"}
        return Mock(ok=True, status_code=200, json=lambda: {"successful": True, "data": data})

    monkeypatch.setattr("src.adapters.composio.requests.post", post)
    monkeypatch.setattr("time.sleep", lambda _: None)
    media = ["a", "b"] if publisher is publish_carousel else "url"
    assert publisher(media, "caption") == "published"
    assert len(ready) == (3 if publisher is publish_carousel else 1)


@pytest.mark.parametrize(
    "status", ["ERROR", "EXPIRED", "PUBLISHED", "UNKNOWN", None, "IN_PROGRESS"]
)
def test_unready_container_never_crosses_publication_boundary(monkeypatch, status):
    events = []
    ticks = iter(range(0, 1000, 30))

    def post(url, **kwargs):
        slug = url.rsplit("/", 1)[-1]
        events.append(slug)
        data = {"status_code": status} if slug == "INSTAGRAM_GET_POST_STATUS" else {"id": "c"}
        return Mock(ok=True, status_code=200, json=lambda: {"successful": True, "data": data})

    monkeypatch.setattr("src.adapters.composio.requests.post", post)
    monkeypatch.setattr("time.sleep", lambda _: None)
    monkeypatch.setattr("time.monotonic", lambda: next(ticks))
    callback = Mock()
    error_type = (
        TimeoutError
        if status == "IN_PROGRESS"
        else ComposioActionError
        if status in ("ERROR", "EXPIRED", "PUBLISHED")
        else ComposioResponseError
    )
    with pytest.raises(error_type):
        publish_image_post("url", "caption", before_publish=callback)
    callback.assert_not_called()
    assert "INSTAGRAM_CREATE_POST" not in events
    assert 1 <= events.count("INSTAGRAM_GET_POST_STATUS") <= 4
