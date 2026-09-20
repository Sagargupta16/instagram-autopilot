"""Publish a multi-image Instagram carousel (N+2 step flow).

Flow: N child containers (one per image, is_carousel_item=true, no caption)
-> 1 carousel container (caption goes here) -> publish.

location_id lives on the PARENT container only. Meta explicitly rejects
it on child containers -- see docs/specs/2026-07-03-v2-premium-multi-slot.md.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from src.adapters.composio import ComposioResponseError, execute_action
from src.publishing.boundaries import create_with_location, media_id, validate_alt_text
from src.publishing.readiness import wait_until_ready
from src.settings import settings

log = logging.getLogger(__name__)


def _create_child_container(
    image_url: str, index: int, total: int, *, alt_text: str | None = None
) -> str:
    log.info("Creating carousel child %d/%d...", index + 1, total)
    params = {
        "ig_user_id": settings.instagram_user_id,
        "image_url": image_url,
        "is_carousel_item": True,
    }
    if alt_text is not None:
        params["alt_text"] = alt_text
    result = execute_action(
        "INSTAGRAM_CREATE_MEDIA_CONTAINER",
        params=params,
    )
    return media_id(result, "INSTAGRAM_CREATE_MEDIA_CONTAINER")


def _create_parent_container(params: dict[str, Any], location_id: str | None) -> dict:
    return create_with_location(
        execute_action, "INSTAGRAM_CREATE_CAROUSEL_CONTAINER", params, location_id
    )


def publish_carousel(
    image_urls: list[str],
    caption: str,
    *,
    location_id: str | None = None,
    before_publish: Callable[[str], None] | None = None,
    alt_texts: list[str] | None = None,
) -> str:
    """Return the media ID; callback must durably record publishing or raise.

    Any error after the callback leaves an uncertain outcome for the caller.
    """
    _validate_images(image_urls, alt_texts)
    child_ids = []
    for index, url in enumerate(image_urls):
        options = {"alt_text": alt_texts[index]} if alt_texts is not None else {}
        child_id = _create_child_container(url, index, len(image_urls), **options)
        if child_id in child_ids:
            raise ComposioResponseError("Carousel child container IDs must be unique")
        wait_until_ready(child_id, execute_action)
        child_ids.append(child_id)

    log.info("Creating carousel container with %d children...", len(child_ids))
    carousel = _create_parent_container(
        {
            "ig_user_id": settings.instagram_user_id,
            "children": child_ids,
            "caption": caption,
        },
        location_id,
    )
    carousel_id = media_id(carousel, "INSTAGRAM_CREATE_CAROUSEL_CONTAINER")
    log.info("Carousel container created: %s", carousel_id)

    wait_until_ready(carousel_id, execute_action)

    log.info("Publishing carousel to Instagram...")
    params = {"ig_user_id": settings.instagram_user_id, "creation_id": carousel_id}
    if before_publish is not None:
        before_publish(carousel_id)
    published = execute_action(
        "INSTAGRAM_CREATE_POST",
        params=params,
    )
    identifier = media_id(published, "INSTAGRAM_CREATE_POST")
    log.info("Published carousel! Media ID: %s (%d slides)", identifier, len(image_urls))
    return identifier


def _validate_images(image_urls: list[str], alt_texts: list[str] | None) -> None:
    if not isinstance(image_urls, list) or not 2 <= len(image_urls) <= 10:
        raise ValueError("Carousel requires 2 to 10 images")
    if any(not isinstance(url, str) or not url.strip() for url in image_urls):
        raise ValueError("Carousel image URLs must be non-empty strings")
    if alt_texts is not None:
        if not isinstance(alt_texts, list) or len(alt_texts) != len(image_urls):
            raise ValueError("alt_texts must have one description per carousel image")
        for text in alt_texts:
            if text is None:
                raise ValueError("alt_texts entries must be strings")
            validate_alt_text(text)
