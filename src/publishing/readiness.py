"""Poll documented draft status before crossing the durable publication boundary."""

from __future__ import annotations

import time

from src.adapters.composio import ComposioActionError, ComposioResponseError, validate_action_result
from src.publishing.boundaries import ActionExecutor

STATUS_ACTION = "INSTAGRAM_GET_POST_STATUS"
POLL_INTERVAL_SECONDS = 3


def wait_until_ready(
    creation_id: str, execute: ActionExecutor, *, max_wait_seconds: int = 60
) -> None:
    """Require FINISHED; deadlines and a poll cap bound pending containers.

    Schema verified at https://docs.composio.dev/toolkits/instagram on 2026-09-20.
    CREATE_POST has no wait parameters; GET_POST_STATUS accepts creation_id.
    """
    deadline = time.monotonic() + max_wait_seconds
    for _ in range(max_wait_seconds // POLL_INTERVAL_SECONDS + 1):
        result = validate_action_result(
            execute(STATUS_ACTION, params={"creation_id": creation_id}), STATUS_ACTION
        )
        status = result["data"].get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED", "PUBLISHED"):
            raise ComposioActionError(
                f"Container {creation_id} cannot be published: {status}",
                action_slug=STATUS_ACTION,
                result=result,
            )
        if status != "IN_PROGRESS":
            raise ComposioResponseError(f"{STATUS_ACTION}: missing or unknown container status")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))
    raise TimeoutError(f"Container {creation_id} was not ready within {max_wait_seconds}s")
