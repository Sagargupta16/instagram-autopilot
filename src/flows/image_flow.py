"""Generate one AI image and publish as a single Instagram post.

Iterates through image_prompts until one survives Stability's filter,
so a filter hit on prompt[0] doesn't kill the slot.
"""

from __future__ import annotations

import logging
from typing import Any

from src.adapters.cloudinary_host import upload_image
from src.adapters.places import resolve_location_id
from src.media.image import ImageFilteredError, generate_image
from src.publishing.image_post import publish_image_post

log = logging.getLogger(__name__)


def post_image(
    caption_data: dict[str, Any], caption: str, image_model: str, *, dry_run: bool
) -> None:
    """Generate the first non-filtered image and publish it."""
    prompts = caption_data.get("image_prompts") or [caption_data.get("image_prompt", "")]
    image_bytes: bytes | None = None
    for i, prompt in enumerate(prompts):
        log.info("Image prompt %d/%d: %s", i + 1, len(prompts), prompt[:120])
        try:
            image_bytes = generate_image(prompt=prompt, model_id=image_model)
            break
        except ImageFilteredError as e:
            log.warning("Image prompt %d/%d filtered -- trying next: %s", i + 1, len(prompts), e)
            continue

    if image_bytes is None:
        raise RuntimeError(f"All {len(prompts)} image prompts filtered by Stability")

    if dry_run:
        log.info("DRY RUN: Generated %d bytes of image data", len(image_bytes))
        return

    image_url = upload_image(image_bytes)
    location_id = resolve_location_id(caption_data.get("location_query") or "")
    publish_image_post(image_url=image_url, caption=caption, location_id=location_id)
