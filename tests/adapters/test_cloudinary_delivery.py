from __future__ import annotations

import io
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

from src.adapters import cloudinary_host as host


@pytest.fixture
def jpeg() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (1080, 1350), "red").save(output, "JPEG")
    return output.getvalue()


@pytest.fixture
def delivery(monkeypatch, jpeg):
    url = "https://res.cloudinary.com/test/image/upload/v1/a.jpg"
    upload = Mock(
        return_value={
            "secure_url": url,
            "format": "jpg",
            "width": 1080,
            "height": 1350,
            "bytes": len(jpeg),
            "type": "upload",
        }
    )
    response = Mock(headers={"Content-Type": "image/jpeg"}, url=url, status_code=200)
    response.iter_content.return_value = [jpeg]
    get = Mock(return_value=response)
    monkeypatch.setattr(host.cloudinary.uploader, "upload", upload)
    monkeypatch.setattr(requests, "get", get)
    return upload, get, response, url


def test_public_jpeg_delivery_is_checked_with_actual_get(delivery, jpeg) -> None:
    upload, get, _, url = delivery
    assert host.upload_image(jpeg) == url
    assert upload.call_args.kwargs["type"] == "upload"
    assert upload.call_args.kwargs["format"] == "jpg"
    assert upload.call_args.kwargs["access_control"] == [{"access_type": "anonymous"}]
    assert get.call_args.kwargs["stream"] is True
    assert get.call_args.kwargs["allow_redirects"] is False


def test_html_delivery_fails_even_when_status_is_success(delivery, jpeg) -> None:
    _, _, response, _ = delivery
    response.headers = {"Content-Type": "text/html"}
    response.iter_content.return_value = [b"<html>Not an image</html>"]
    with pytest.raises(ValueError, match="JPEG"):
        host.upload_image(jpeg)


def test_delivery_with_png_bytes_is_rejected(delivery, jpeg) -> None:
    _, _, response, _ = delivery
    response.iter_content.return_value = [b"\x89PNG bad"]
    with pytest.raises(ValueError):
        host.upload_image(jpeg)


def test_private_delivery_is_rejected_before_fetch(delivery, jpeg) -> None:
    upload, get, _, _ = delivery
    upload.return_value["secure_url"] = "https://res.cloudinary.com/test/image/authenticated/a.jpg"
    with pytest.raises(ValueError, match="public"):
        host.upload_image(jpeg)
    get.assert_not_called()


def test_stream_stops_at_byte_limit(delivery, jpeg) -> None:
    _, _, response, _ = delivery
    response.iter_content.return_value = [b"x" * 4_000_001, b"x" * 4_000_001]
    with pytest.raises(ValueError, match="size"):
        host.upload_image(jpeg)
    response.close.assert_called_once()


def test_redirect_is_not_accepted_as_public_delivery(delivery, jpeg) -> None:
    _, _, response, _ = delivery
    response.status_code = 302
    with pytest.raises(ValueError, match="200"):
        host.upload_image(jpeg)


def test_incompatible_input_is_rejected_before_upload(delivery) -> None:
    upload, _, _, _ = delivery
    with pytest.raises(ValueError):
        host.upload_image(b"not an image")
    upload.assert_not_called()
