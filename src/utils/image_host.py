"""Upload images to Cloudinary for public URL hosting."""

from __future__ import annotations

import io
import logging

import cloudinary
import cloudinary.uploader

log = logging.getLogger(__name__)


def configure_cloudinary(cloud_name: str, api_key: str, api_secret: str) -> None:
    cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret)


def upload_image(image_bytes: bytes) -> str:
    """Upload image bytes to Cloudinary and return the direct URL.

    Accepts raw image bytes (PNG/JPEG). Cloudinary URLs are trusted by
    Instagram's Graph API (unlike imgbb which Meta blocks).
    """
    result = cloudinary.uploader.upload(
        io.BytesIO(image_bytes),
        folder="instagram-autopilot",
        resource_type="image",
    )
    url: str = result["secure_url"]
    log.info("Image uploaded to Cloudinary: %s", url)
    return url
