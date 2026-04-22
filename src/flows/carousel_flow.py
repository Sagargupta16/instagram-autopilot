"""Generate 5 AI images and publish as an Instagram carousel."""

from __future__ import annotations

import logging
from typing import Any

from src.adapters.cloudinary_host import upload_image
from src.media.image import generate_image
from src.publishing.carousel import publish_carousel

log = logging.getLogger(__name__)


def post_carousel(
    caption_data: dict[str, Any], caption: str, image_model: str, *, dry_run: bool
) -> None:
    """Generate each slide's image, upload, and publish as a carousel."""
    image_prompts: list[str] = caption_data["image_prompts"]
    image_urls: list[str] = []

    for i, prompt in enumerate(image_prompts):
        log.info("Slide %d/%d prompt: %s", i + 1, len(image_prompts), prompt[:120])
        image_bytes = generate_image(prompt=prompt, model_id=image_model)
        log.info("Slide %d: %d bytes", i + 1, len(image_bytes))
        if not dry_run:
            image_urls.append(upload_image(image_bytes))

    if dry_run:
        log.info("DRY RUN: Generated %d carousel slides", len(image_prompts))
        return

    publish_carousel(image_urls=image_urls, caption=caption)
