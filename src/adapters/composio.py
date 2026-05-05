"""Composio v3 REST API client for Instagram publishing actions."""

from __future__ import annotations

import logging
import time

import requests

from src.settings import settings

log = logging.getLogger(__name__)

API_URL = "https://backend.composio.dev/api/v3/tools/execute"
CONNECTED_ACCOUNT_URL = "https://backend.composio.dev/api/v3/connected_accounts/{id}"

# Retry tuning for transient failures. ComposioActionError (successful=false from
# Instagram's Graph API) is NOT retried -- it's a semantic error, not a blip.
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 2


class ComposioActionError(Exception):
    """Raised when a Composio v3 action returns successful=false."""


def _post_with_retry(url: str, body: dict, headers: dict, timeout: int) -> requests.Response:
    """POST with exponential backoff on network errors and 5xx responses."""
    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            last_exc = e
            if attempt == MAX_ATTEMPTS - 1:
                raise
            wait = BACKOFF_BASE_SECONDS**attempt
            log.warning(
                "Composio network error (attempt %d/%d): %s -- retrying in %ds",
                attempt + 1,
                MAX_ATTEMPTS,
                e,
                wait,
            )
            time.sleep(wait)
            continue
        # Retry 5xx only; 4xx is our fault and won't get better by waiting.
        if resp.status_code >= 500 and attempt < MAX_ATTEMPTS - 1:
            wait = BACKOFF_BASE_SECONDS**attempt
            log.warning(
                "Composio %d (attempt %d/%d) -- retrying in %ds: %s",
                resp.status_code,
                attempt + 1,
                MAX_ATTEMPTS,
                wait,
                resp.text[:200],
            )
            time.sleep(wait)
            continue
        return resp
    # Unreachable, but satisfies type checkers.
    raise last_exc or RuntimeError("Composio retry loop exited without response")


def verify_auth() -> None:
    """Smoke-test Composio creds before committing to a run.

    Reads the configured connected account -- cheap, no side effects. Fails fast
    so a bad key does not waste the 0-180 min jitter sleep.
    """
    if not settings.composio_connected_account_id:
        log.warning("Composio preflight skipped: COMPOSIO_CONNECTED_ACCOUNT_ID not set")
        return
    url = CONNECTED_ACCOUNT_URL.format(id=settings.composio_connected_account_id)
    resp = requests.get(url, headers={"x-api-key": settings.composio_api_key}, timeout=15)
    if not resp.ok:
        log.error("Composio auth preflight FAILED %s: %s", resp.status_code, resp.text[:300])
        resp.raise_for_status()
    log.info("Composio auth preflight OK")


def execute_action(action_slug: str, params: dict) -> dict:
    """Execute a Composio v3 action against the configured Instagram account.

    Reads auth from settings so callers don't have to pass them. Retries
    transient 5xx / network errors (up to MAX_ATTEMPTS). Raises
    ComposioActionError if the action returns successful=false (v3 wraps
    Instagram API errors in a 200 response).
    """
    body = {
        "arguments": params,
        "connected_account_id": settings.composio_connected_account_id,
        "user_id": settings.composio_user_id,
    }
    resp = _post_with_retry(
        f"{API_URL}/{action_slug}",
        body=body,
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
