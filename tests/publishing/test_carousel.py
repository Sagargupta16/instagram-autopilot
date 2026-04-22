"""Tests for carousel publishing (N+2 step flow)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
