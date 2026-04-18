"""Publish content to Instagram via Composio REST API."""

from __future__ import annotations

import logging
import time

import requests

from src.publisher.composio_auth import resolve_connected_account_id

log = logging.getLogger(__name__)

COMPOSIO_API_URL = "https://backend.composio.dev/api/v2/actions"


def _execute_action(
    action_slug: str,
    params: dict,
    api_key: str,
    connected_account_id: str,
) -> dict:
    """Execute a Composio action via REST API."""
    resolved_id = resolve_connected_account_id(api_key, "instagram", connected_account_id)
    body: dict = {
        "entityId": "default",
        "appName": "instagram",
        "input": params,
    }
    if resolved_id:
        body["connectedAccountId"] = resolved_id

    resp = requests.post(
        f"{COMPOSIO_API_URL}/{action_slug}/execute",
        json=body,
        headers={"x-api-key": api_key},
        timeout=120,
    )
    if not resp.ok:
        log.error("Composio %s returned %s: %s", action_slug, resp.status_code, resp.text)
        resp.raise_for_status()
    return resp.json()


def publish_image_post(
    image_url: str,
    caption: str,
    api_key: str,
    ig_user_id: str,
    connected_account_id: str = "",
) -> str:
    """Publish a single image post to Instagram (two-step container flow)."""
    log.info("Creating Instagram media container...")
    container_result = _execute_action(
        action_slug="INSTAGRAM_POST_IG_USER_MEDIA",
        params={
            "ig_user_id": ig_user_id,
            "image_url": image_url,
            "caption": caption,
        },
        api_key=api_key,
        connected_account_id=connected_account_id,
    )

    creation_id = container_result["data"]["id"]
    log.info("Container created: %s", creation_id)

    time.sleep(3)

    log.info("Publishing to Instagram...")
    publish_result = _execute_action(
        action_slug="INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH",
        params={
            "ig_user_id": ig_user_id,
            "creation_id": creation_id,
            "max_wait_seconds": 60,
        },
        api_key=api_key,
        connected_account_id=connected_account_id,
    )

    media_id = publish_result["data"]["id"]
    log.info("Published image post! Media ID: %s", media_id)
    return media_id


def publish_reel(
    video_url: str,
    caption: str,
    api_key: str,
    ig_user_id: str,
    connected_account_id: str = "",
) -> str:
    """Publish a Reel to Instagram (two-step container flow with video)."""
    log.info("Creating Instagram Reel container...")
    container_result = _execute_action(
        action_slug="INSTAGRAM_POST_IG_USER_MEDIA",
        params={
            "ig_user_id": ig_user_id,
            "video_url": video_url,
            "caption": caption,
            "media_type": "REELS",
            "share_to_feed": True,
        },
        api_key=api_key,
        connected_account_id=connected_account_id,
    )

    creation_id = container_result["data"]["id"]
    log.info("Reel container created: %s", creation_id)

    log.info("Waiting for Reel to process...")
    publish_result = _execute_action(
        action_slug="INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH",
        params={
            "ig_user_id": ig_user_id,
            "creation_id": creation_id,
            "max_wait_seconds": 120,
            "poll_interval_seconds": 5,
        },
        api_key=api_key,
        connected_account_id=connected_account_id,
    )

    media_id = publish_result["data"]["id"]
    log.info("Published Reel! Media ID: %s", media_id)
    return media_id
