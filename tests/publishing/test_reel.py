"""Tests for Reel publishing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.publishing.reel import publish_reel


class TestPublishReel:
    @patch("src.publishing.reel.execute_action")
    @patch("src.publishing.reel.wait_until_ready")
    def test_two_step_with_reels_media_type(
        self, mock_ready: MagicMock, mock_exec: MagicMock
    ) -> None:
        mock_exec.side_effect = [
            {"data": {"id": "reel_container"}, "successful": True},
            {"data": {"id": "reel_media"}, "successful": True},
        ]
        media_id = publish_reel("s3://bucket/v.mp4", "reel caption")
        assert media_id == "reel_media"
        assert mock_exec.call_count == 2

        container_call = mock_exec.call_args_list[0]
        params = container_call.kwargs["params"]
        assert container_call.args[0] == "INSTAGRAM_CREATE_MEDIA_CONTAINER"
        assert params["media_type"] == "REELS"
        assert params["share_to_feed"] is True
        assert params["video_url"] == "s3://bucket/v.mp4"
        assert "thumb_offset" not in params  # Instagram's default first frame

    @patch("src.publishing.reel.execute_action")
    @patch("src.publishing.reel.wait_until_ready")
    def test_thumb_offset_sets_the_cover_frame_in_milliseconds(
        self, mock_ready: MagicMock, mock_exec: MagicMock
    ) -> None:
        mock_exec.side_effect = [
            {"data": {"id": "reel_container"}, "successful": True},
            {"data": {"id": "reel_media"}, "successful": True},
        ]
        assert publish_reel("https://v.example/a.mp4", "c", thumb_offset=15300) == "reel_media"
        params = mock_exec.call_args_list[0].kwargs["params"]
        assert params["thumb_offset"] == 15300
        assert isinstance(params["thumb_offset"], int)
        assert "audio_name" not in params  # the container tool has no audio_name field
        assert "thumb_offset" not in mock_exec.call_args_list[1].kwargs["params"]
