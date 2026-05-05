"""Publish an Instagram Reel (video, 2-step with longer processing wait)."""

from __future__ import annotations

import logging

from src.adapters.composio import execute_action
from src.settings import settings

log = logging.getLogger(__name__)

# Reels take longer to transcode server-side than images; give Composio
# more headroom in its poll loop.
REEL_PUBLISH_MAX_WAIT_SECONDS = 120
REEL_POLL_INTERVAL_SECONDS = 5


def publish_reel(video_url: str, caption: str) -> str:
    """Publish a Reel. Returns the Instagram media ID."""
    log.info("Creating Instagram Reel container...")
    container = execute_action(
        "INSTAGRAM_CREATE_MEDIA_CONTAINER",
        params={
            "ig_user_id": settings.instagram_user_id,
            "video_url": video_url,
            "caption": caption,
            "media_type": "REELS",
            "share_to_feed": True,
        },
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
