"""Tests for Cloudinary adapter."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.cloudinary_host import upload_image, verify_auth


class TestUploadImage:
    @patch("src.adapters.cloudinary_host.cloudinary.uploader.upload")
    def test_returns_secure_url(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/x/img.png"}
        url = upload_image(b"\x89PNG" + b"\x00" * 50)
        assert url == "https://res.cloudinary.com/x/img.png"

    @patch("src.adapters.cloudinary_host.cloudinary.uploader.upload")
    def test_uploads_to_date_bucketed_folder(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = {"secure_url": "https://x.com/img.png"}
        upload_image(b"data")
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
