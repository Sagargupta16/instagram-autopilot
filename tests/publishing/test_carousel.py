"""Tests for carousel publishing (N+2 step flow)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.adapters.composio import ComposioActionError
from src.publishing.carousel import publish_carousel


class TestPublishCarousel:
    @patch("src.publishing.carousel.execute_action")
    @patch("src.publishing.carousel.time.sleep")
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
    @patch("src.publishing.carousel.time.sleep")
    def test_location_id_only_on_parent_never_on_children(
        self, mock_sleep: MagicMock, mock_exec: MagicMock
    ) -> None:
        """LOAD-BEARING: Meta rejects location_id on carousel children. Must go on parent only."""

        def _stub(slug: str, params: dict) -> dict:
            if slug == "INSTAGRAM_POST_IG_USER_MEDIA":
                assert "location_id" not in params, "location_id must NOT be on carousel children"
                return {"data": {"id": f"child-{params.get('image_url', '?')[-1]}"}}
            if slug == "INSTAGRAM_CREATE_CAROUSEL_CONTAINER":
                assert params["location_id"] == "loc-42", "parent must receive location_id"
                return {"data": {"id": "carousel-ok"}}
            if slug == "INSTAGRAM_CREATE_POST":
                return {"data": {"id": "media-final"}}
            raise AssertionError(f"unexpected slug {slug}")

        mock_exec.side_effect = _stub

        publish_carousel(
            image_urls=["https://ex.com/a", "https://ex.com/b"],
            caption="c",
            location_id="loc-42",
        )

    @patch("src.publishing.carousel.execute_action")
    @patch("src.publishing.carousel.time.sleep")
    def test_retries_parent_without_location_on_invalid_id(
        self, mock_sleep: MagicMock, mock_exec: MagicMock
    ) -> None:
        parent_calls = {"count": 0}

        def _stub(slug: str, params: dict) -> dict:
            if slug == "INSTAGRAM_POST_IG_USER_MEDIA":
                return {"data": {"id": "child-1"}}
            if slug == "INSTAGRAM_CREATE_CAROUSEL_CONTAINER":
                parent_calls["count"] += 1
                if parent_calls["count"] == 1:
                    raise ComposioActionError(
                        "INSTAGRAM_PLATFORM_API__INVALID_LOCATION_ID: bad page id"
                    )
                assert "location_id" not in params
                return {"data": {"id": "carousel-ok"}}
            if slug == "INSTAGRAM_CREATE_POST":
                return {"data": {"id": "media-final"}}
            raise AssertionError(slug)

        mock_exec.side_effect = _stub

        publish_carousel(["https://ex.com/a"], "c", location_id="bad-loc")

        assert parent_calls["count"] == 2
