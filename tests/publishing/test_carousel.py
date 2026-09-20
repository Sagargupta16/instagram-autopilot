"""Tests for carousel publishing (N+2 step flow)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.adapters.composio import ComposioActionError, ComposioResponseError
from src.publishing.carousel import publish_carousel


class TestPublishCarousel:
    @patch("src.publishing.carousel.execute_action")
    @patch("src.publishing.carousel.wait_until_ready")
    def test_multi_step_flow(self, mock_sleep: MagicMock, mock_exec: MagicMock) -> None:
        mock_exec.side_effect = [
            {"data": {"id": "child_1"}, "successful": True},
            {"data": {"id": "child_2"}, "successful": True},
            {"data": {"id": "child_3"}, "successful": True},
            {"data": {"id": "carousel_c"}, "successful": True},
            {"data": {"id": "media_final"}, "successful": True},
        ]

        media_id = publish_carousel(
            image_urls=[
                "https://example.com/1.png",
                "https://example.com/2.png",
                "https://example.com/3.png",
            ],
            caption="carousel test",
        )
        assert media_id == "media_final"
        assert mock_exec.call_count == 5

        child_call = mock_exec.call_args_list[0]
        assert child_call.kwargs["params"]["is_carousel_item"] is True
        assert "caption" not in child_call.kwargs["params"]

        carousel_call = mock_exec.call_args_list[3]
        assert carousel_call.args[0] == "INSTAGRAM_CREATE_CAROUSEL_CONTAINER"
        assert carousel_call.kwargs["params"]["children"] == ["child_1", "child_2", "child_3"]
        assert carousel_call.kwargs["params"]["caption"] == "carousel test"

    @patch("src.publishing.carousel.execute_action")
    @patch("src.publishing.carousel.wait_until_ready")
    def test_location_id_only_on_parent_never_on_children(
        self, mock_sleep: MagicMock, mock_exec: MagicMock
    ) -> None:
        """LOAD-BEARING: Meta rejects location_id on carousel children. Must go on parent only."""

        def _stub(slug: str, params: dict) -> dict:
            if slug == "INSTAGRAM_CREATE_MEDIA_CONTAINER":
                assert "location_id" not in params, "location_id must NOT be on carousel children"
                return {"successful": True, "data": {"id": f"child-{params['image_url'][-1]}"}}
            if slug == "INSTAGRAM_CREATE_CAROUSEL_CONTAINER":
                assert params["location_id"] == "loc-42", "parent must receive location_id"
                return {"successful": True, "data": {"id": "carousel-ok"}}
            if slug == "INSTAGRAM_CREATE_POST":
                return {"successful": True, "data": {"id": "media-final"}}
            raise AssertionError(f"unexpected slug {slug}")

        mock_exec.side_effect = _stub

        publish_carousel(
            image_urls=["https://ex.com/a", "https://ex.com/b"],
            caption="c",
            location_id="loc-42",
        )

    @patch("src.publishing.carousel.execute_action")
    @patch("src.publishing.carousel.wait_until_ready")
    def test_retries_parent_without_location_on_invalid_id(
        self, mock_sleep: MagicMock, mock_exec: MagicMock
    ) -> None:
        parent_calls = {"count": 0}

        def _stub(slug: str, params: dict) -> dict:
            if slug == "INSTAGRAM_CREATE_MEDIA_CONTAINER":
                return {"successful": True, "data": {"id": f"child-{params['image_url'][-1]}"}}
            if slug == "INSTAGRAM_CREATE_CAROUSEL_CONTAINER":
                parent_calls["count"] += 1
                if parent_calls["count"] == 1:
                    raise ComposioActionError(
                        "INSTAGRAM_PLATFORM_API__INVALID_LOCATION_ID: bad page id"
                    )
                assert "location_id" not in params
                return {"successful": True, "data": {"id": "carousel-ok"}}
            if slug == "INSTAGRAM_CREATE_POST":
                return {"successful": True, "data": {"id": "media-final"}}
            raise AssertionError(slug)

        mock_exec.side_effect = _stub

        publish_carousel(["https://ex.com/a", "https://ex.com/b"], "c", location_id="bad-loc")

        assert parent_calls["count"] == 2


@pytest.mark.parametrize("count", [2, 10])
def test_accepts_both_slide_count_bounds(monkeypatch, count):
    execute = MagicMock(
        side_effect=[
            {"successful": True, "data": {"id": f"container-{index}"}} for index in range(count + 2)
        ]
    )
    monkeypatch.setattr("src.publishing.carousel.execute_action", execute)
    monkeypatch.setattr("src.publishing.carousel.wait_until_ready", lambda *args: None)
    assert (
        publish_carousel(["https://example.com/image.jpg"] * count, "caption")
        == f"container-{count + 1}"
    )
    parent = execute.call_args_list[count]
    assert parent.kwargs["params"]["children"] == [f"container-{index}" for index in range(count)]
    assert all("alt_text" not in call.kwargs["params"] for call in execute.call_args_list)


def test_duplicate_child_ids_never_create_parent(monkeypatch):
    execute = MagicMock(return_value={"successful": True, "data": {"id": "same-child"}})
    monkeypatch.setattr("src.publishing.carousel.execute_action", execute)
    monkeypatch.setattr("src.publishing.carousel.wait_until_ready", lambda *args: None)
    callback = MagicMock()
    with pytest.raises(ComposioResponseError):
        publish_carousel(["a", "b"], "caption", before_publish=callback)
    callback.assert_not_called()
    assert execute.call_count == 2
    assert all(
        call.args[0] == "INSTAGRAM_CREATE_MEDIA_CONTAINER" for call in execute.call_args_list
    )


@pytest.mark.parametrize("identifier", ["", None, 123])
def test_invalid_parent_id_never_reaches_callback(monkeypatch, identifier):
    execute = MagicMock(
        side_effect=[
            {"successful": True, "data": {"id": "child-1"}},
            {"successful": True, "data": {"id": "child-2"}},
            {"successful": True, "data": {"id": identifier}},
        ]
    )
    monkeypatch.setattr("src.publishing.carousel.execute_action", execute)
    monkeypatch.setattr("src.publishing.carousel.wait_until_ready", lambda *args: None)
    callback = MagicMock()
    with pytest.raises(ComposioResponseError):
        publish_carousel(["a", "b"], "caption", before_publish=callback)
    callback.assert_not_called()
    assert execute.call_count == 3
