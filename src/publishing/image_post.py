"""Publish a single-image Instagram post (2-step: container -> publish)."""

from __future__ import annotations

import logging
import time
from typing import Any

from src.adapters.composio import ComposioActionError, execute_action
from src.settings import settings

log = logging.getLogger(__name__)

CONTAINER_PROCESS_WAIT_SECONDS = 3
PUBLISH_MAX_WAIT_SECONDS = 60


def _is_invalid_location(err: ComposioActionError) -> bool:
    msg = str(err).lower()
    return "invalid_location_id" in msg or "9004" in msg


def _create_container(params: dict[str, Any], location_id: str | None) -> dict:
    if location_id:
        params = {**params, "location_id": location_id}
    try:
        return execute_action("INSTAGRAM_POST_IG_USER_MEDIA", params=params)
    except ComposioActionError as e:
        if location_id and _is_invalid_location(e):
            log.warning("Image container rejected location_id=%s -- retrying without", location_id)
            params = {k: v for k, v in params.items() if k != "location_id"}
            return execute_action("INSTAGRAM_POST_IG_USER_MEDIA", params=params)
        raise


def publish_image_post(
    image_url: str, caption: str, *, location_id: str | None = None
) -> str:
    """Publish a single image post. Returns the Instagram media ID."""
    log.info("Creating Instagram media container...")
    container = _create_container(
        {
            "ig_user_id": settings.instagram_user_id,
            "image_url": image_url,
            "caption": caption,
        },
        location_id,
    )
    creation_id = container["data"]["id"]
    log.info("Container created: %s", creation_id)

    time.sleep(CONTAINER_PROCESS_WAIT_SECONDS)

    log.info("Publishing to Instagram...")
    published = execute_action(
        "INSTAGRAM_CREATE_POST",
        params={
            "ig_user_id": settings.instagram_user_id,
            "creation_id": creation_id,
            "max_wait_seconds": PUBLISH_MAX_WAIT_SECONDS,
        },
    )
    media_id: str = published["data"]["id"]
    log.info("Published image post! Media ID: %s", media_id)
    return media_id
