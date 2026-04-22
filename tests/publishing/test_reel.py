"""Tests for Reel publishing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.publishing.reel import publish_reel


class TestPublishReel:
    @patch("src.publishing.reel.execute_action")
    def test_two_step_with_reels_media_type(self, mock_exec: MagicMock) -> None:
        mock_exec.side_effect = [
            {"data": {"id": "reel_container"}, "successful": True},
            {"data": {"id": "reel_media"}, "successful": True},
        ]
        media_id = publish_reel("s3://bucket/v.mp4", "reel caption")
        assert media_id == "reel_media"
        assert mock_exec.call_count == 2

        container_call = mock_exec.call_args_list[0]
        params = container_call.kwargs["params"]
        assert params["media_type"] == "REELS"
        assert params["share_to_feed"] is True
        assert params["video_url"] == "s3://bucket/v.mp4"
