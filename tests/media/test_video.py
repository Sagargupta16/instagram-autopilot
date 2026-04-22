"""Tests for Nova Reel async video generation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.media.video import generate_video


class TestGenerateVideo:
    @patch("src.media.video.time.sleep")
    @patch("src.media.video.get_async_invocation_status")
    @patch("src.media.video.start_async_invocation")
    def test_polls_until_complete(
        self,
        mock_start: MagicMock,
        mock_status: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        mock_start.return_value = "arn:aws:bedrock:job-123"
        mock_status.side_effect = [
            {"status": "InProgress"},
            {
                "status": "Completed",
                "outputDataConfig": {"s3OutputDataConfig": {"s3Uri": "s3://bucket/output"}},
            },
        ]

        result = generate_video(
            prompt="test",
            model_id="amazon.nova-reel-v1:0",
            s3_output_uri="s3://bucket/",
            poll_interval=1,
        )
        assert result == "s3://bucket/output/output.mp4"
        assert mock_status.call_count == 2
