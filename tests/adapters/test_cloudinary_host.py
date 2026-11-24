"""Tests for Cloudinary adapter."""

from __future__ import annotations

import io
import re
from unittest.mock import MagicMock, patch

import cloudinary.exceptions
import pytest
from PIL import Image

from src.adapters.cloudinary_host import upload_image, upload_video, verify_auth


def image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (1080, 1350)).save(buffer, "JPEG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def delivery_get():
    with patch("src.adapters.cloudinary_host.requests.get") as get:
        get.return_value.status_code = 200
        get.return_value.headers = {"Content-Type": "image/jpeg"}
        get.return_value.iter_content.return_value = [image_bytes()]
        yield


class TestUploadImage:
    @patch("src.adapters.cloudinary_host.cloudinary.uploader.upload")
    def test_returns_secure_url(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = {
            "secure_url": "https://res.cloudinary.com/x/image/upload/img.jpg"
        }
        url = upload_image(image_bytes())
        assert url == "https://res.cloudinary.com/x/image/upload/img.jpg"

    @patch("src.adapters.cloudinary_host.cloudinary.uploader.upload")
    def test_uploads_to_date_bucketed_folder(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = {
            "secure_url": "https://res.cloudinary.com/x/image/upload/img.jpg"
        }
        upload_image(image_bytes())
        kwargs = mock_upload.call_args.kwargs
        # Folder is "instagram-autopilot/YYYY-MM" so monthly cleanup is trivial.
        assert re.match(r"^instagram-autopilot/\d{4}-\d{2}$", kwargs["folder"])
        assert kwargs["resource_type"] == "image"


class TestUploadVideo:
    @patch("src.adapters.cloudinary_host.cloudinary.uploader.upload")
    def test_stores_the_bytes_without_a_conversion(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = {
            "secure_url": "https://res.cloudinary.com/x/video/upload/v1/reel.mp4"
        }

        url = upload_video(b"mp4 bytes")

        kwargs = mock_upload.call_args.kwargs
        assert url == "https://res.cloudinary.com/x/video/upload/v1/reel.mp4"
        assert kwargs["resource_type"] == "video"
        # A requested format makes Cloudinary process the video inside the upload call.
        assert "format" not in kwargs

    @patch("src.adapters.cloudinary_host.cloudinary.uploader.upload")
    def test_a_refused_upload_logs_cloudinarys_reason(
        self, mock_upload: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        mock_upload.side_effect = cloudinary.exceptions.BadRequest("Video is too large")

        with pytest.raises(cloudinary.exceptions.BadRequest):
            upload_video(b"12345")

        assert "Cloudinary rejected the video upload (5 bytes): Video is too large" in caplog.text


class TestVerifyAuth:
    @patch("src.adapters.cloudinary_host.cloudinary.api.ping")
    def test_ok_does_not_raise(self, mock_ping: MagicMock) -> None:
        mock_ping.return_value = {"status": "ok"}
        verify_auth()
        assert mock_ping.call_count == 1

    @patch("src.adapters.cloudinary_host.cloudinary.api.ping")
    def test_raises_on_bad_creds(self, mock_ping: MagicMock) -> None:
        mock_ping.side_effect = RuntimeError("invalid creds")
        with pytest.raises(RuntimeError, match="invalid creds"):
            verify_auth()
