"""Publish an Instagram Reel (video, 2-step with longer processing wait)."""

from __future__ import annotations

import logging
from typing import Any

from src.adapters.composio import ComposioActionError, execute_action
from src.settings import settings

log = logging.getLogger(__name__)

# Reels take longer to transcode server-side than images; give Composio
# more headroom in its poll loop.
REEL_PUBLISH_MAX_WAIT_SECONDS = 120
REEL_POLL_INTERVAL_SECONDS = 5


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
            log.warning("Reel container rejected location_id=%s -- retrying without", location_id)
            params = {k: v for k, v in params.items() if k != "location_id"}
            return execute_action("INSTAGRAM_POST_IG_USER_MEDIA", params=params)
        raise


def publish_reel(
    video_url: str, caption: str, *, location_id: str | None = None
) -> str:
    """Publish a Reel. Returns the Instagram media ID."""
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
    creation_id = container["data"]["id"]
    log.info("Reel container created: %s", creation_id)

    log.info("Waiting for Reel to process...")
    published = execute_action(
        "INSTAGRAM_CREATE_POST",
        params={
            "ig_user_id": settings.instagram_user_id,
            "creation_id": creation_id,
            "max_wait_seconds": REEL_PUBLISH_MAX_WAIT_SECONDS,
            "poll_interval_seconds": REEL_POLL_INTERVAL_SECONDS,
        },
    )
    media_id: str = published["data"]["id"]
    log.info("Published Reel! Media ID: %s", media_id)
    return media_id
