"""Publish content to X/Twitter via Composio SDK."""

from __future__ import annotations

import logging

from composio import Action, ComposioToolSet

log = logging.getLogger(__name__)


def publish_text_post(text: str, api_key: str) -> str | None:
    """Publish a text-only post to X/Twitter.

    Returns the tweet ID on success, None if X is not connected.
    """
    toolset = ComposioToolSet(api_key=api_key)

    try:
        result = toolset.execute_action(
            action=Action.TWITTER_CREATION_OF_A_POST,
            params={"text": text},
        )
        # Tweet ID can be nested in various response formats
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
