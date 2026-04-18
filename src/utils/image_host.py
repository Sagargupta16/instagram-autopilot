"""Upload images to imgbb for public URL hosting."""

from __future__ import annotations

import base64
import logging

import requests

log = logging.getLogger(__name__)

IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"


def upload_to_imgbb(image_bytes: bytes, api_key: str) -> str:
    """Upload image bytes to imgbb and return the direct URL.

    Accepts raw image bytes (PNG/JPEG) -- no file I/O needed.
    Auto-expires after 24 hours (Instagram fetches during container
    creation, then hosts its own copy).
    """
    image_data = base64.b64encode(image_bytes).decode()

    resp = requests.post(
        IMGBB_UPLOAD_URL,
        data={
            "key": api_key,
            "image": image_data,
            "expiration": 86400,
        },
        timeout=30,
    )
    resp.raise_for_status()

    result = resp.json()
    url = result["data"]["url"]
    log.info("Image uploaded to imgbb: %s", url)
    return url
