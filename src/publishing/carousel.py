"""Publish a multi-image Instagram carousel (N+2 step flow).

Flow: N child containers (one per image, is_carousel_item=true, no caption)
-> 1 carousel container (caption goes here) -> publish.
"""

from __future__ import annotations

import logging
import time

from src.adapters.composio import execute_action
from src.settings import settings

log = logging.getLogger(__name__)


def _create_child_container(image_url: str, index: int, total: int) -> str:
    log.info("Creating carousel child %d/%d...", index + 1, total)
    result = execute_action(
        "INSTAGRAM_CREATE_MEDIA_CONTAINER",
        params={
            "ig_user_id": settings.instagram_user_id,
            "image_url": image_url,
            "is_carousel_item": True,
        },
    )
    return result["data"]["id"]


def publish_carousel(image_urls: list[str], caption: str) -> str:
    """Publish a carousel of images. Returns the Instagram media ID."""
    child_ids = [
        _create_child_container(url, i, len(image_urls)) for i, url in enumerate(image_urls)
    ]

    time.sleep(3)

    log.info("Creating carousel container with %d children...", len(child_ids))
    carousel = execute_action(
        "INSTAGRAM_CREATE_CAROUSEL_CONTAINER",
        params={
            "ig_user_id": settings.instagram_user_id,
            "children": child_ids,
            "caption": caption,
        },
    )
    carousel_id = carousel["data"]["id"]
    log.info("Carousel container created: %s", carousel_id)

    time.sleep(3)

    log.info("Publishing carousel to Instagram...")
    published = execute_action(
        "INSTAGRAM_CREATE_POST",
        params={
            "ig_user_id": settings.instagram_user_id,
            "creation_id": carousel_id,
            "max_wait_seconds": 60,
        },
    )
    media_id: str = published["data"]["id"]
    log.info("Published carousel! Media ID: %s (%d slides)", media_id, len(image_urls))
    return media_id
