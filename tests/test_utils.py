"""Tests for utility functions (image hosting, image generation, reel generation)."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch


class TestImageHost:
    @patch("src.utils.image_host.cloudinary.uploader.upload")
    def test_upload_returns_secure_url(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = {
            "secure_url": "https://res.cloudinary.com/test/image/upload/v1/instagram-autopilot/abc123.png",
        }

        from src.utils.image_host import upload_image

        url = upload_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        assert (
            url == "https://res.cloudinary.com/test/image/upload/v1/instagram-autopilot/abc123.png"
        )
        mock_upload.assert_called_once()

    @patch("src.utils.image_host.cloudinary.uploader.upload")
    def test_uploads_to_correct_folder(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/test/img.png"}

        from src.utils.image_host import upload_image

        upload_image(b"fake image data")

        call_kwargs = mock_upload.call_args.kwargs
        assert call_kwargs["folder"] == "instagram-autopilot"
        assert call_kwargs["resource_type"] == "image"


class TestImageGenerator:
    @patch("src.generator.image.requests.post")
    def test_returns_image_bytes(self, mock_post: MagicMock) -> None:
        fake_image = b"\x89PNG fake image bytes"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"images": [base64.b64encode(fake_image).decode()]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from src.generator.image import generate_image

        result = generate_image(prompt="test prompt", model_id="amazon.nova-canvas-v1:0")
        assert result == fake_image

    @patch("src.generator.image.requests.post")
    def test_sends_correct_body(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"images": [base64.b64encode(b"img").decode()]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from src.generator.image import generate_image

        generate_image(prompt="a cool image", model_id="amazon.nova-canvas-v1:0")

        call_body = mock_post.call_args.kwargs["json"]
        assert call_body["taskType"] == "TEXT_IMAGE"
        assert call_body["textToImageParams"]["text"] == "a cool image"
        assert call_body["imageGenerationConfig"]["width"] == 1024
        assert call_body["imageGenerationConfig"]["height"] == 1024


class TestReelGenerator:
    @patch("src.generator.reel.time.sleep")
    @patch("src.generator.reel.requests.get")
    @patch("src.generator.reel.requests.post")
    def test_polls_until_complete(
        self, mock_post: MagicMock, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        # Start job response
        mock_start_resp = MagicMock()
        mock_start_resp.json.return_value = {"invocationArn": "arn:aws:bedrock:job-123"}
        mock_start_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_start_resp

        # Poll responses: InProgress -> Completed
        mock_poll_1 = MagicMock()
        mock_poll_1.json.return_value = {"status": "InProgress"}
        mock_poll_1.raise_for_status = MagicMock()

        mock_poll_2 = MagicMock()
        mock_poll_2.json.return_value = {
            "status": "Completed",
            "outputDataConfig": {"s3OutputDataConfig": {"s3Uri": "s3://bucket/output"}},
        }
        mock_poll_2.raise_for_status = MagicMock()

        mock_get.side_effect = [mock_poll_1, mock_poll_2]

        from src.generator.reel import generate_reel

        result = generate_reel(
            prompt="test video",
            model_id="amazon.nova-reel-v1:0",
            s3_output_uri="s3://bucket/",
            poll_interval=1,
        )
        assert result == "s3://bucket/output/output.mp4"
        assert mock_get.call_count == 2
