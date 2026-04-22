"""Composio v3 REST API client for Instagram publishing actions."""

from __future__ import annotations

import logging

import requests

from src.settings import settings

log = logging.getLogger(__name__)

API_URL = "https://backend.composio.dev/api/v3/tools/execute"


class ComposioActionError(Exception):
    """Raised when a Composio v3 action returns successful=false."""


def execute_action(action_slug: str, params: dict) -> dict:
    """Execute a Composio v3 action against the configured Instagram account.

    Reads auth details from settings so callers don't have to pass them.
    Raises ComposioActionError if the action returns successful=false
    (v3 wraps Instagram API errors in a 200 response).
    """
    body = {
        "arguments": params,
        "connected_account_id": settings.composio_connected_account_id,
        "user_id": settings.composio_user_id,
    }
    resp = requests.post(
        f"{API_URL}/{action_slug}",
        json=body,
        headers={"x-api-key": settings.composio_api_key},
        timeout=120,
    )
    if not resp.ok:
        log.error("Composio %s returned %s: %s", action_slug, resp.status_code, resp.text)
        resp.raise_for_status()

    result = resp.json()
    if not result.get("successful", True):
        error_msg = result.get("error") or result.get("data", {}).get("message", "Unknown error")
        log.error("Composio %s failed: %s", action_slug, error_msg)
        raise ComposioActionError(f"{action_slug}: {error_msg}")
    return result
