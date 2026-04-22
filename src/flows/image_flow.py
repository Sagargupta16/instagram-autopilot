"""Generate one AI image and publish as a single Instagram post."""

from __future__ import annotations

import logging
from typing import Any

from src.adapters.cloudinary_host import upload_image
from src.media.image import generate_image
from src.publishing.image_post import publish_image_post

log = logging.getLogger(__name__)


def post_image(
    caption_data: dict[str, Any], caption: str, image_model: str, *, dry_run: bool
) -> None:
    """Generate the first image from caption_data and publish it."""
    prompts = caption_data.get("image_prompts", [caption_data.get("image_prompt", "")])
    image_prompt = prompts[0]
    log.info("Image prompt: %s", image_prompt)

    image_bytes = generate_image(prompt=image_prompt, model_id=image_model)

    if dry_run:
        log.info("DRY RUN: Generated %d bytes of image data", len(image_bytes))
        return

    image_url = upload_image(image_bytes)
    publish_image_post(image_url=image_url, caption=caption)
