"""Tests for Cloudinary adapter."""

from __future__ import annotations

import io
import re
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.adapters.cloudinary_host import upload_image, verify_auth


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
