"""Validated responses and location fallback shared by Instagram publishers."""

from __future__ import annotations

import re
from typing import Protocol

from src.adapters.composio import (
    ComposioActionError,
    ComposioResponseError,
    validate_action_result,
)


class ActionExecutor(Protocol):
    def __call__(self, action_slug: str, params: dict) -> dict: ...


def media_id(result: object, action_slug: str) -> str:
    identifier = validate_action_result(result, action_slug)["data"].get("id")
    if (
        not isinstance(identifier, str)
        or not identifier.strip()
        or identifier != identifier.strip()
    ):
        raise ComposioResponseError(f"{action_slug}: missing or invalid media/container ID")
    return identifier


def _invalid_location(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            _invalid_location(value.get(key))
            for key in ("error", "data", "message", "code", "type", "error_code", "error_subcode")
        )
    if isinstance(value, list):
        return any(_invalid_location(item) for item in value)
    if isinstance(value, str):
        # Explicit provider identifiers only. 9004/2207052 means media download,
        # and mentions of location in an unrelated failure do not justify retry.
        return (
            re.search(r"\b(?:INSTAGRAM_PLATFORM_API__)?INVALID_LOCATION_ID\b", value, re.I)
            is not None
        )
    return False


def create_with_location(
    execute: ActionExecutor, slug: str, params: dict, location_id: str | None
) -> dict:
    arguments = {**params, "location_id": location_id} if location_id else params
    try:
        return validate_action_result(execute(slug, params=arguments), slug)
    except ComposioActionError as error:
        details = error.result if error.result is not None else str(error)
        if not location_id or not _invalid_location(details):
            raise
        return validate_action_result(execute(slug, params=params), slug)


def validate_alt_text(alt_text: str | None) -> None:
    # Verified 2026-09-20: https://docs.composio.dev/toolkits/instagram
    # CREATE_MEDIA_CONTAINER supports alt_text on images/children, <=1000 chars.
    if alt_text is not None and (
        not isinstance(alt_text, str) or not alt_text.strip() or len(alt_text) > 1000
    ):
        raise ValueError("alt_text must be a non-empty string of at most 1000 characters")
