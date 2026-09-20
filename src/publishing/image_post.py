"""Publish a single-image Instagram post (2-step: container -> publish)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from src.adapters.composio import execute_action
from src.publishing.boundaries import create_with_location, media_id, validate_alt_text
from src.publishing.readiness import wait_until_ready
from src.settings import settings

log = logging.getLogger(__name__)


def _create_container(params: dict[str, Any], location_id: str | None) -> dict:
    return create_with_location(
        execute_action, "INSTAGRAM_CREATE_MEDIA_CONTAINER", params, location_id
    )


def publish_image_post(
    image_url: str,
    caption: str,
    *,
    location_id: str | None = None,
    before_publish: Callable[[str], None] | None = None,
    alt_text: str | None = None,
) -> str:
    """Return the media ID; callback must durably record publishing or raise.

    Any error after the callback leaves an uncertain outcome for the caller.
    """
    validate_alt_text(alt_text)
    log.info("Creating Instagram media container...")
    params = {
        "ig_user_id": settings.instagram_user_id,
        "image_url": image_url,
        "caption": caption,
    }
    if alt_text is not None:
        params["alt_text"] = alt_text
    container = _create_container(params, location_id)
    creation_id = media_id(container, "INSTAGRAM_CREATE_MEDIA_CONTAINER")
    log.info("Container created: %s", creation_id)

    wait_until_ready(creation_id, execute_action)

    log.info("Publishing to Instagram...")
    params = {"ig_user_id": settings.instagram_user_id, "creation_id": creation_id}
    if before_publish is not None:
        before_publish(creation_id)
    published = execute_action(
        "INSTAGRAM_CREATE_POST",
        params=params,
    )
    identifier = media_id(published, "INSTAGRAM_CREATE_POST")
    log.info("Published image post! Media ID: %s", identifier)
    return identifier
