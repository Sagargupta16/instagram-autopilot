"""The connected account's own handle, read live so the Reel end card follows a rename."""

from __future__ import annotations

import logging
import re

from src.adapters.composio import (
    ComposioActionError,
    ComposioRequestError,
    ComposioResponseError,
    execute_action,
)

log = logging.getLogger(__name__)

USERNAME = re.compile(r"[A-Za-z0-9._]{1,30}")  # Instagram's username alphabet and length


def handle() -> str | None:
    """ "@username" of the connected account, or None (logged) when it cannot be read.

    A read-only lookup. None leaves the end card without a handle line rather than showing a
    stale name, and never fails the slot.
    """
    try:
        result = execute_action(
            "INSTAGRAM_GET_USER_INFO", {"ig_user_id": "me", "fields": "username"}
        )
    except (ComposioActionError, ComposioRequestError, ComposioResponseError) as error:
        log.warning("End card without a handle: account lookup failed (%s)", type(error).__name__)
        return None
    name = result["data"].get("username")
    if not isinstance(name, str) or not USERNAME.fullmatch(name):
        log.warning("End card without a handle: the account lookup returned no usable username")
        return None
    return f"@{name}"
