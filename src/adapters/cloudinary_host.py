"""Cloudinary image hosting adapter.

Instagram's Graph API fetches images server-side from the URL we provide.
Meta blocks imgbb, but trusts res.cloudinary.com -- do not swap hosts
without verifying the new domain is accepted.
"""

from __future__ import annotations

import io
import logging

import cloudinary
import cloudinary.uploader

from src.settings import settings

log = logging.getLogger(__name__)


def configure() -> None:
    """Initialize the Cloudinary SDK from settings. Call once at startup."""
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )


def upload_image(image_bytes: bytes) -> str:
    """Upload image bytes and return the public secure URL."""
    result = cloudinary.uploader.upload(
        io.BytesIO(image_bytes),
        folder="instagram-autopilot",
        resource_type="image",
    )
    url: str = result["secure_url"]
    log.info("Image uploaded to Cloudinary: %s", url)
    return url
