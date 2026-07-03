"""Cloudinary image hosting adapter.

Instagram's Graph API fetches images server-side from the URL we provide.
Meta blocks imgbb, but trusts res.cloudinary.com -- do not swap hosts
without verifying the new domain is accepted.
"""

from __future__ import annotations

import io
import logging
from datetime import UTC, datetime

import cloudinary
import cloudinary.api
import cloudinary.uploader

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

    Fails fast so a bad cloud_name/api_key does not waste the jitter sleep.
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
    """Upload image bytes and return the public secure URL."""
    result = cloudinary.uploader.upload(
        io.BytesIO(image_bytes),
        folder=_current_folder(),
        resource_type="image",
    )
    url: str = result["secure_url"]
    log.info("Image uploaded to Cloudinary: %s", url)
    return url


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
    )
    url: str = result["secure_url"]
    log.info("Video uploaded to Cloudinary: %s", url)
    return url
