"""Publish a multi-image Instagram carousel (N+2 step flow).

Flow: N child containers (one per image, is_carousel_item=true, no caption)
-> 1 carousel container (caption goes here) -> publish.

location_id lives on the PARENT container only. Meta explicitly rejects
it on child containers -- see docs/specs/2026-07-03-v2-premium-multi-slot.md.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.adapters.composio import ComposioActionError, execute_action
from src.settings import settings

log = logging.getLogger(__name__)

# How long to let Instagram process a media container before we reference
# it in the next step. Empirically 3s is enough for image containers;
# carousel container processing is handled by max_wait_seconds below.
CONTAINER_PROCESS_WAIT_SECONDS = 3
PUBLISH_MAX_WAIT_SECONDS = 60


def _is_invalid_location(err: ComposioActionError) -> bool:
    msg = str(err).lower()
    return "invalid_location_id" in msg or "9004" in msg


def _create_child_container(image_url: str, index: int, total: int) -> str:
    log.info("Creating carousel child %d/%d...", index + 1, total)
    result = execute_action(
        "INSTAGRAM_POST_IG_USER_MEDIA",
        params={
            "ig_user_id": settings.instagram_user_id,
            "image_url": image_url,
            "is_carousel_item": True,
        },
    )
    return result["data"]["id"]


def _create_parent_container(params: dict[str, Any], location_id: str | None) -> dict:
    if location_id:
        params = {**params, "location_id": location_id}
    try:
        return execute_action("INSTAGRAM_CREATE_CAROUSEL_CONTAINER", params=params)
    except ComposioActionError as e:
        if location_id and _is_invalid_location(e):
            log.warning(
                "Carousel rejected location_id=%s -- retrying without", location_id
            )
            params = {k: v for k, v in params.items() if k != "location_id"}
            return execute_action("INSTAGRAM_CREATE_CAROUSEL_CONTAINER", params=params)
        raise


def publish_carousel(
    image_urls: list[str], caption: str, *, location_id: str | None = None
) -> str:
    """Publish a carousel of images. Returns the Instagram media ID."""
    child_ids = [
        _create_child_container(url, i, len(image_urls))
        for i, url in enumerate(image_urls)
    ]

    time.sleep(CONTAINER_PROCESS_WAIT_SECONDS)

    log.info("Creating carousel container with %d children...", len(child_ids))
    carousel = _create_parent_container(
        {
            "ig_user_id": settings.instagram_user_id,
            "children": child_ids,
            "caption": caption,
        },
        location_id,
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
