"""Tests for Cloudinary adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.adapters.cloudinary_host import upload_image


class TestUploadImage:
    @patch("src.adapters.cloudinary_host.cloudinary.uploader.upload")
    def test_returns_secure_url(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/x/img.png"}
        url = upload_image(b"\x89PNG" + b"\x00" * 50)
        assert url == "https://res.cloudinary.com/x/img.png"

    @patch("src.adapters.cloudinary_host.cloudinary.uploader.upload")
    def test_uploads_to_correct_folder(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = {"secure_url": "https://x.com/img.png"}
        upload_image(b"data")
        kwargs = mock_upload.call_args.kwargs
        assert kwargs["folder"] == "instagram-autopilot"
        assert kwargs["resource_type"] == "image"
