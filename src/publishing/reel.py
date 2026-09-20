"""Publish an Instagram Reel (video, 2-step with longer processing wait)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from src.adapters.composio import execute_action
from src.publishing.boundaries import create_with_location, media_id
from src.publishing.readiness import wait_until_ready
from src.settings import settings

log = logging.getLogger(__name__)

# Reels take longer to transcode server-side than images; give Composio
# more headroom in its poll loop.
REEL_PUBLISH_MAX_WAIT_SECONDS = 120


def _create_container(params: dict[str, Any], location_id: str | None) -> dict:
    return create_with_location(
        execute_action, "INSTAGRAM_CREATE_MEDIA_CONTAINER", params, location_id
    )


def publish_reel(
    video_url: str,
    caption: str,
    *,
    location_id: str | None = None,
    before_publish: Callable[[str], None] | None = None,
) -> str:
    """Return the media ID; callback must durably record publishing or raise.

    Any error after the callback leaves an uncertain outcome for the caller.
    """
    log.info("Creating Instagram Reel container...")
    container = _create_container(
        {
            "ig_user_id": settings.instagram_user_id,
            "video_url": video_url,
            "caption": caption,
            "media_type": "REELS",
            "share_to_feed": True,
        },
        location_id,
    )
    creation_id = media_id(container, "INSTAGRAM_CREATE_MEDIA_CONTAINER")
    log.info("Reel container created: %s", creation_id)

    log.info("Waiting for Reel to process...")
    wait_until_ready(creation_id, execute_action, max_wait_seconds=REEL_PUBLISH_MAX_WAIT_SECONDS)
    params = {"ig_user_id": settings.instagram_user_id, "creation_id": creation_id}
    if before_publish is not None:
        before_publish(creation_id)
    published = execute_action(
        "INSTAGRAM_CREATE_POST",
        params=params,
    )
    identifier = media_id(published, "INSTAGRAM_CREATE_POST")
    log.info("Published Reel! Media ID: %s", identifier)
    return identifier
