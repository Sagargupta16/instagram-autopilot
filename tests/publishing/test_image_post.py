"""Tests for single image publishing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.publishing.image_post import publish_image_post


class TestPublishImagePost:
    @patch("src.publishing.image_post.execute_action")
    @patch("src.publishing.image_post.time.sleep")
    def test_two_step_flow_returns_media_id(
        self, mock_sleep: MagicMock, mock_exec: MagicMock
    ) -> None:
        mock_exec.side_effect = [
            {"data": {"id": "container_123"}, "successful": True},
            {"data": {"id": "media_456"}, "successful": True},
        ]
        media_id = publish_image_post("https://example.com/img.png", "caption")
        assert media_id == "media_456"
        assert mock_exec.call_count == 2

        first_call = mock_exec.call_args_list[0]
        assert first_call.args[0] == "INSTAGRAM_CREATE_MEDIA_CONTAINER"
        assert first_call.kwargs["params"]["image_url"] == "https://example.com/img.png"

        second_call = mock_exec.call_args_list[1]
        assert second_call.args[0] == "INSTAGRAM_CREATE_POST"
        assert second_call.kwargs["params"]["creation_id"] == "container_123"
