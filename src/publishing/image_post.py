"""Publish a single-image Instagram post (2-step: container -> publish)."""

from __future__ import annotations

import logging
import time

from src.adapters.composio import execute_action
from src.settings import settings

log = logging.getLogger(__name__)


def publish_image_post(image_url: str, caption: str) -> str:
    """Publish a single image post. Returns the Instagram media ID."""
    log.info("Creating Instagram media container...")
    container = execute_action(
        "INSTAGRAM_CREATE_MEDIA_CONTAINER",
        params={
            "ig_user_id": settings.instagram_user_id,
            "image_url": image_url,
            "caption": caption,
        },
    )
    creation_id = container["data"]["id"]
    log.info("Container created: %s", creation_id)

    time.sleep(3)

    log.info("Publishing to Instagram...")
    published = execute_action(
        "INSTAGRAM_CREATE_POST",
        params={
            "ig_user_id": settings.instagram_user_id,
            "creation_id": creation_id,
            "max_wait_seconds": 60,
        },
    )
    media_id: str = published["data"]["id"]
    log.info("Published image post! Media ID: %s", media_id)
    return media_id
