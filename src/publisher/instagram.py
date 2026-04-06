"""Publish content to Instagram via Composio SDK."""

from __future__ import annotations

import logging
import time

from composio import Action, ComposioToolSet

log = logging.getLogger(__name__)

IG_USER_ID = "25519335194405950"  # @sagar_sethh


def publish_image_post(
    image_url: str,
    caption: str,
    api_key: str,
) -> str:
    """Publish a single image post to Instagram.

    Two-step process:
    1. Create media container (draft) with image URL + caption
    2. Publish the container

    Returns the published media ID.
    """
    toolset = ComposioToolSet(api_key=api_key)

    # Step 1: Create media container
    log.info("Creating Instagram media container...")
    container_result = toolset.execute_action(
        action=Action.INSTAGRAM_POST_IG_USER_MEDIA,
        params={
            "ig_user_id": IG_USER_ID,
            "image_url": image_url,
            "caption": caption,
        },
    )

    creation_id = container_result["data"]["id"]
    log.info("Container created: %s", creation_id)

    # Brief pause for Instagram to process the container
    time.sleep(3)

    # Step 2: Publish
    log.info("Publishing to Instagram...")
    publish_result = toolset.execute_action(
        action=Action.INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH,
        params={
            "ig_user_id": IG_USER_ID,
            "creation_id": creation_id,
            "max_wait_seconds": 60,
        },
    )

    media_id = publish_result["data"]["id"]
    log.info("Published! Media ID: %s", media_id)
    return media_id
