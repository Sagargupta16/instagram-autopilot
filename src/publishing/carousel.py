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

# How long to let Instagram process a media container before we reference
# it in the next step. Empirically 3s is enough for image containers;
# carousel container processing is handled by max_wait_seconds below.
CONTAINER_PROCESS_WAIT_SECONDS = 3
PUBLISH_MAX_WAIT_SECONDS = 60


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

    time.sleep(CONTAINER_PROCESS_WAIT_SECONDS)

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

    time.sleep(CONTAINER_PROCESS_WAIT_SECONDS)

    log.info("Publishing carousel to Instagram...")
    published = execute_action(
        "INSTAGRAM_CREATE_POST",
        params={
            "ig_user_id": settings.instagram_user_id,
            "creation_id": carousel_id,
            "max_wait_seconds": PUBLISH_MAX_WAIT_SECONDS,
        },
    )
    media_id: str = published["data"]["id"]
    log.info("Published carousel! Media ID: %s (%d slides)", media_id, len(image_urls))
    return media_id
