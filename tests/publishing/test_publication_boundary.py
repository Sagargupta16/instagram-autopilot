"""Exercise publication boundaries through the real adapter, with HTTP replaced."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.adapters.composio import ComposioActionError, ComposioResponseError
from src.publishing.carousel import publish_carousel
from src.publishing.image_post import publish_image_post
from src.publishing.reel import publish_reel

PUBLISHERS = [
    (publish_carousel, ["https://example.com/1.jpg", "https://example.com/2.jpg"]),
    (publish_image_post, "https://example.com/image.jpg"),
    (publish_reel, "https://example.com/video.mp4"),
]


@pytest.fixture
def remote(monkeypatch):
    events = []
    responses = {}
    containers = []

    def post(url, *, json, headers, timeout):
        slug = url.rsplit("/", 1)[-1]
        params = json["arguments"]
        events.append((slug, params))
        if slug in responses:
            result = responses[slug]
        elif slug == "INSTAGRAM_GET_POST_STATUS":
            result = {"successful": True, "data": {"status_code": "FINISHED"}}
        elif slug == "INSTAGRAM_CREATE_POST":
            result = {"successful": True, "data": {"id": "media-final"}}
        else:
            identifier = f"container-{len(containers) + 1}"
            containers.append(identifier)
            result = {"successful": True, "data": {"id": identifier}}
        return Mock(ok=True, status_code=200, json=lambda: result)

    monkeypatch.setattr("src.adapters.composio.requests.post", post)
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    return events, responses, containers


@pytest.mark.parametrize(("publisher", "media"), PUBLISHERS)
def test_durable_callback_is_immediately_before_final_request(remote, publisher, media):
    events, _, containers = remote

    def before_publish(creation_id):
        assert creation_id == containers[-1]
        events.append(("durable-publishing", creation_id))

    assert publisher(media, "caption", before_publish=before_publish) == "media-final"
    assert events[-2] == ("durable-publishing", containers[-1])
    assert events[-1][0] == "INSTAGRAM_CREATE_POST"
    assert events[-1][1] == {"ig_user_id": "123456", "creation_id": containers[-1]}
    assert sum(event[0] == "durable-publishing" for event in events) == 1


@pytest.mark.parametrize(("publisher", "media"), PUBLISHERS)
def test_callback_failure_prevents_publication(remote, publisher, media):
    events, _, _ = remote

    def fail_persistence(creation_id):
        raise OSError("durable record unavailable")

    with pytest.raises(OSError, match="durable record"):
        publisher(media, "caption", before_publish=fail_persistence)
    assert not any(slug == "INSTAGRAM_CREATE_POST" for slug, _ in events)


@pytest.mark.parametrize(("publisher", "media"), PUBLISHERS)
@pytest.mark.parametrize("identifier", [None, "", " ", 123, True, [], {}])
def test_invalid_container_id_never_reaches_callback(remote, publisher, media, identifier):
    events, responses, _ = remote
    responses["INSTAGRAM_CREATE_MEDIA_CONTAINER"] = {"successful": True, "data": {"id": identifier}}
    callback = Mock()
    with pytest.raises(ComposioResponseError):
        publisher(media, "caption", before_publish=callback)
    callback.assert_not_called()
    assert len(events) == 1


@pytest.mark.parametrize(("publisher", "media"), PUBLISHERS)
@pytest.mark.parametrize(
    "result",
    [
        {"successful": True, "data": {}},
        {"successful": True, "data": {"id": ""}},
        {"successful": True, "data": {"id": 123}},
        {"data": {"id": "media"}},
        {"successful": "true", "data": {"id": "media"}},
    ],
)
def test_malformed_publication_result_is_uncertain(remote, publisher, media, result):
    events, responses, _ = remote
    responses["INSTAGRAM_CREATE_POST"] = result
    callback = Mock()
    with pytest.raises(ComposioResponseError):
        publisher(media, "caption", before_publish=callback)
    callback.assert_called_once()
    assert sum(slug == "INSTAGRAM_CREATE_POST" for slug, _ in events) == 1


@pytest.mark.parametrize(("publisher", "media"), PUBLISHERS)
def test_media_download_error_does_not_retry_without_location(remote, publisher, media):
    events, responses, _ = remote
    failing_slug = (
        "INSTAGRAM_CREATE_CAROUSEL_CONTAINER"
        if publisher is publish_carousel
        else "INSTAGRAM_CREATE_MEDIA_CONTAINER"
    )
    responses[failing_slug] = {
        "successful": False,
        "error": {"code": 9004, "error_subcode": 2207052, "message": "Media download failed"},
    }
    with pytest.raises(ComposioActionError):
        publisher(media, "caption", location_id="location-42")
    assert sum(slug == failing_slug for slug, _ in events) == 1
    assert not any(slug == "INSTAGRAM_CREATE_POST" for slug, _ in events)


def test_alt_text_sent_only_to_corresponding_image_containers(remote):
    events, _, _ = remote
    publish_carousel(PUBLISHERS[0][1], "caption", alt_texts=["First image", "Second image"])
    children = [params for slug, params in events if slug == "INSTAGRAM_CREATE_MEDIA_CONTAINER"]
    assert [params["alt_text"] for params in children] == ["First image", "Second image"]
    assert all(
        "alt_text" not in params
        for slug, params in events
        if slug != "INSTAGRAM_CREATE_MEDIA_CONTAINER"
    )
    events.clear()
    publish_image_post("https://example.com/image.jpg", "caption", alt_text="Image description")
    assert events[0][1]["alt_text"] == "Image description"


@pytest.mark.parametrize("images", [[], ["a"], ["a"] * 11, "ab", ["a", ""], ["a", None]])
def test_invalid_carousel_input_fails_before_remote_work(remote, images):
    events, _, _ = remote
    with pytest.raises(ValueError):
        publish_carousel(images, "caption")
    assert events == []


@pytest.mark.parametrize(
    "texts", [[], ["one"], ["one", None], ["one", ""], ["one", "x" * 1001], "ab"]
)
def test_invalid_alt_text_fails_before_remote_work(remote, texts):
    events, _, _ = remote
    with pytest.raises(ValueError):
        publish_carousel(PUBLISHERS[0][1], "caption", alt_texts=texts)
    assert events == []
