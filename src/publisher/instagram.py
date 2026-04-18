"""Publish content to Instagram via Composio SDK."""

from __future__ import annotations

import logging
import time

from composio import Action, ComposioToolSet

log = logging.getLogger(__name__)


def publish_image_post(
    image_url: str,
    caption: str,
    api_key: str,
    ig_user_id: str,
    entity_id: str = "default",
) -> str:
    """Publish a single image post to Instagram (two-step container flow)."""
    toolset = ComposioToolSet(api_key=api_key, entity_id=entity_id)

    log.info("Creating Instagram media container...")
    container_result = toolset.execute_action(
        action=Action.INSTAGRAM_POST_IG_USER_MEDIA,
        params={
            "ig_user_id": ig_user_id,
            "image_url": image_url,
            "caption": caption,
        },
    )

    creation_id = container_result["data"]["id"]
    log.info("Container created: %s", creation_id)

    time.sleep(3)

    log.info("Publishing to Instagram...")
    publish_result = toolset.execute_action(
        action=Action.INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH,
        params={
            "ig_user_id": ig_user_id,
            "creation_id": creation_id,
            "max_wait_seconds": 60,
        },
    )

    media_id = publish_result["data"]["id"]
    log.info("Published image post! Media ID: %s", media_id)
    return media_id


def publish_reel(
    video_url: str,
    caption: str,
    api_key: str,
    ig_user_id: str,
    entity_id: str = "default",
) -> str:
    """Publish a Reel to Instagram (two-step container flow with video)."""
    toolset = ComposioToolSet(api_key=api_key, entity_id=entity_id)

    log.info("Creating Instagram Reel container...")
    container_result = toolset.execute_action(
        action=Action.INSTAGRAM_POST_IG_USER_MEDIA,
        params={
            "ig_user_id": ig_user_id,
            "video_url": video_url,
            "caption": caption,
            "media_type": "REELS",
            "share_to_feed": True,
        },
    )

    creation_id = container_result["data"]["id"]
    log.info("Reel container created: %s", creation_id)

    # Reels take longer to process than images
    log.info("Waiting for Reel to process...")
    publish_result = toolset.execute_action(
        action=Action.INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH,
        params={
            "ig_user_id": ig_user_id,
            "creation_id": creation_id,
            "max_wait_seconds": 120,
            "poll_interval_seconds": 5,
        },
    )

    media_id = publish_result["data"]["id"]
    log.info("Published Reel! Media ID: %s", media_id)
    return media_id
