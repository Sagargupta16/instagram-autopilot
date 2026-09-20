"""Cloudinary image hosting adapter.

Instagram's Graph API fetches images server-side from the URL we provide.
Meta blocks imgbb, but trusts res.cloudinary.com -- do not swap hosts
without verifying the new domain is accepted.
"""

from __future__ import annotations

import io
import logging
from datetime import UTC, datetime
from urllib.parse import urlsplit

import cloudinary
import cloudinary.api
import cloudinary.uploader
import requests

from src.media.image_normalization import MAX_IMAGE_BYTES, validate_instagram_image
from src.settings import settings

log = logging.getLogger(__name__)

BASE_FOLDER = "instagram-autopilot"


def configure() -> None:
    """Initialize the Cloudinary SDK from settings. Call once at startup."""
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )


def verify_auth() -> None:
    """Ping the Cloudinary admin API to confirm credentials.

    Fails before paid media generation when hosting credentials are invalid.
    Must be called after configure().
    """
    try:
        cloudinary.api.ping()
    except Exception:  # cloudinary raises its own exception types; re-wrap.
        log.exception("Cloudinary auth preflight FAILED")
        raise
    log.info("Cloudinary auth preflight OK")


def _current_folder() -> str:
    """Bucket uploads by YYYY-MM so free-tier cleanup is trivial."""
    return f"{BASE_FOLDER}/{datetime.now(UTC).strftime('%Y-%m')}"


def upload_image(image_bytes: bytes) -> str:
    """Check anonymous JPEG delivery; Meta's own processing still decides fetchability."""
    validate_instagram_image(image_bytes)
    result = cloudinary.uploader.upload(
        io.BytesIO(image_bytes),
        folder=_current_folder(),
        resource_type="image",
        type="upload",
        format="jpg",
        access_control=[{"access_type": "anonymous"}],
        overwrite=False,
    )
    url: str = result["secure_url"]
    _validate_public_url(url, "image", ".jpg")
    delivered_bytes = _check_image_delivery(url)
    log.info("Cloudinary JPEG checked: 1080x1350, %d bytes; Meta fetch pending", delivered_bytes)
    return url


def _validate_public_url(url: str, resource: str, suffix: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "res.cloudinary.com"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or f"/{resource}/upload/" not in parsed.path
        or not parsed.path.lower().endswith(suffix)
    ):
        raise ValueError("Cloudinary delivery must be a public HTTPS upload URL")


def _check_image_delivery(url: str) -> int:
    response = requests.get(url, timeout=(15, 60), stream=True, allow_redirects=False)
    try:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Cloudinary image delivery must return HTTP 200 directly")
        if response.headers.get("Content-Type", "").split(";")[0].lower() != "image/jpeg":
            raise ValueError("Cloudinary must deliver JPEG content")
        data = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            data.extend(chunk)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError("Cloudinary image exceeds Instagram size limit")
        validate_instagram_image(bytes(data))
        return len(data)
    finally:
        response.close()


def upload_video(video_bytes: bytes) -> str:
    """Upload video bytes and return the public secure URL.

    Uses the same Cloudinary tenant as images -- IG's Graph API trusts
    res.cloudinary.com for both. Free-tier accounts count video against
    the same 25 credits/month bucket; 5s reels are ~1-3 credits each.
    """
    result = cloudinary.uploader.upload(
        io.BytesIO(video_bytes),
        folder=_current_folder(),
        resource_type="video",
        type="upload",
        format="mp4",
        access_control=[{"access_type": "anonymous"}],
        overwrite=False,
    )
    url: str = result["secure_url"]
    _validate_public_url(url, "video", ".mp4")
    log.info("Video uploaded to Cloudinary: %s", url)
    return url
