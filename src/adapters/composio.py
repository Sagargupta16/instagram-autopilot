"""Composio v3 REST API client for Instagram publishing actions."""

from __future__ import annotations

import logging
import math
import time

import requests

from src.settings import settings

log = logging.getLogger(__name__)

API_URL = "https://backend.composio.dev/api/v3/tools/execute"
CONNECTED_ACCOUNT_URL = "https://backend.composio.dev/api/v3/connected_accounts/{id}"

# Only these operations are safe to replay; container retries may leave drafts,
# but cannot publish. Unknown actions, including final publication, get one try.
RETRYABLE_ACTIONS = frozenset(
    {
        "INSTAGRAM_CREATE_MEDIA_CONTAINER",
        "INSTAGRAM_CREATE_CAROUSEL_CONTAINER",
        "INSTAGRAM_GET_POST_STATUS",
    }
)
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 2
HTTP_TIMEOUT_MARGIN_SECONDS = 30


class ComposioActionError(Exception):
    """A definite unsuccessful action result, retaining structured provider details."""

    def __init__(
        self, message: str, *, action_slug: str | None = None, result: dict | None = None
    ) -> None:
        super().__init__(message)
        self.action_slug = action_slug
        self.result = result


class ComposioRequestError(requests.RequestException):
    """Transport/HTTP failure: the remote action's outcome is unknown."""


class ComposioResponseError(Exception):
    """Malformed or contradictory response: success cannot be established."""


def _post_with_retry(
    url: str, body: dict, headers: dict, timeout: float, *, attempts: int
) -> requests.Response:
    """Bounded retry for explicitly safe operations only."""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            last_exc = e
            if attempt == attempts - 1:
                raise
            wait = BACKOFF_BASE_SECONDS**attempt
            log.warning(
                "Composio network error (attempt %d/%d): %s -- retrying in %ds",
                attempt + 1,
                attempts,
                e,
                wait,
            )
            time.sleep(wait)
            continue
        # Retry 5xx only; 4xx is our fault and won't get better by waiting.
        if resp.status_code >= 500 and attempt < attempts - 1:
            wait = BACKOFF_BASE_SECONDS**attempt
            log.warning(
                "Composio %d (attempt %d/%d) -- retrying in %ds: %s",
                resp.status_code,
                attempt + 1,
                attempts,
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
    so a bad key does not waste paid image generation.
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

    Publication is never replayed automatically. Only explicit unsuccessful
    results are ComposioActionError; request/response errors are ambiguous.
    """
    body = {
        "arguments": params,
        "connected_account_id": settings.composio_connected_account_id,
        "user_id": settings.composio_user_id,
    }
    wait = params.get("max_wait_seconds", 0)
    if (
        isinstance(wait, bool)
        or not isinstance(wait, (int, float))
        or not math.isfinite(wait)
        or wait < 0
    ):
        raise ValueError("max_wait_seconds must be a finite non-negative number")
    try:
        resp = _post_with_retry(
            f"{API_URL}/{action_slug}",
            body=body,
            headers={"x-api-key": settings.composio_api_key},
            timeout=max(120, wait + HTTP_TIMEOUT_MARGIN_SECONDS),
            attempts=MAX_ATTEMPTS if action_slug in RETRYABLE_ACTIONS else 1,
        )
        resp.raise_for_status()
    except requests.RequestException as error:
        raise ComposioRequestError(f"{action_slug}: request outcome unknown") from error
    try:
        result = resp.json()
    except ValueError as error:
        raise ComposioResponseError(f"{action_slug}: invalid JSON response") from error
    return validate_action_result(result, action_slug)


def validate_action_result(result: object, action_slug: str) -> dict:
    """Require the documented boolean outcome and a usable response payload."""
    if not isinstance(result, dict) or type(result.get("successful")) is not bool:
        raise ComposioResponseError(f"{action_slug}: missing or invalid successful flag")
    if result["successful"] is False:
        data = result.get("data")
        message = (
            result.get("error")
            or (data.get("message") if isinstance(data, dict) else None)
            or "Unknown error"
        )
        raise ComposioActionError(
            f"{action_slug}: {message}", action_slug=action_slug, result=result
        )
    if result.get("error") or not isinstance(result.get("data"), dict):
        raise ComposioResponseError(f"{action_slug}: malformed success response")
    return result
