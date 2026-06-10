"""Tests for Luma Ray 2 async video generation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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
            model_id="luma.ray-v2:0",
            s3_output_uri="s3://bucket/",
            poll_interval=1,
        )
        assert result == "s3://bucket/output/output.mp4"
        assert mock_status.call_count == 2

    @patch("src.media.video.time.sleep")
    @patch("src.media.video.get_async_invocation_status")
    @patch("src.media.video.start_async_invocation")
    def test_sends_luma_ray_request_shape(
        self,
        mock_start: MagicMock,
        mock_status: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        mock_start.return_value = "arn:aws:bedrock:job-123"
        mock_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {"s3OutputDataConfig": {"s3Uri": "s3://b/o"}},
        }

        generate_video(
            prompt="ocean waves",
            model_id="luma.ray-v2:0",
            s3_output_uri="s3://bucket/",
            duration_seconds=9,
            poll_interval=1,
        )

        body = mock_start.call_args[0][1]
        assert body["modelInput"]["prompt"] == "ocean waves"
        assert body["modelInput"]["duration"] == "9s"
        assert body["modelInput"]["aspect_ratio"] == "9:16"
        assert body["modelInput"]["resolution"] == "720p"

    def test_rejects_unsupported_duration(self) -> None:
        with pytest.raises(ValueError, match="durations"):
            generate_video(
                prompt="x",
                model_id="luma.ray-v2:0",
                s3_output_uri="s3://bucket/",
                duration_seconds=6,
            )
