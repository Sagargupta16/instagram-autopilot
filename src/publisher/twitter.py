"""Publish content to X/Twitter via Composio REST API."""

from __future__ import annotations

import logging

import requests

from src.publisher.composio_auth import resolve_connected_account_id

log = logging.getLogger(__name__)

COMPOSIO_API_URL = "https://backend.composio.dev/api/v2/actions"


def publish_text_post(text: str, api_key: str, connected_account_id: str = "") -> str | None:
    """Publish a text-only post to X/Twitter.

    Returns the tweet ID on success, None if X is not connected.
    """
    try:
        resolved_id = resolve_connected_account_id(api_key, "twitter", connected_account_id)
        body: dict = {
            "entityId": "default",
            "appName": "twitter",
            "input": {"text": text},
        }
        if resolved_id:
            body["connectedAccountId"] = resolved_id

        resp = requests.post(
            f"{COMPOSIO_API_URL}/TWITTER_CREATION_OF_A_POST/execute",
            json=body,
            headers={"x-api-key": api_key},
            timeout=60,
        )
        if not resp.ok:
            log.warning("X/Twitter posting failed (%s): %s", resp.status_code, resp.text)
            return None

        result = resp.json()
        data = result.get("data", result)
        tweet_id = (
            data.get("id")
            or data.get("data", {}).get("id")
            or data.get("data", {}).get("data", {}).get("id")
        )
        log.info("Published to X! Tweet ID: %s", tweet_id)
        return tweet_id
    except Exception:
        log.warning("X/Twitter posting failed (account may not be connected yet)")
        return None
