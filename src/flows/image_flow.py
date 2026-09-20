"""Generate one AI image and publish as a single Instagram post.

Iterates through image_prompts until one survives Stability's filter,
so a filter hit on prompt[0] doesn't kill the slot.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from src.adapters.cloudinary_host import upload_image
from src.adapters.places import resolve_location_id
from src.flows.previews import image_items, save_preview
from src.media.image import ImageFilteredError, generate_image
from src.publishing.image_post import publish_image_post

log = logging.getLogger(__name__)


def post_image(
    caption_data: dict[str, Any],
    caption: str,
    image_model: str,
    *,
    dry_run: bool,
    before_publish: Callable[[str], None] | None = None,
) -> str | None:
    """Generate the first non-filtered image and publish it."""
    prompts = image_items(caption_data)
    image_bytes: bytes | None = None
    alt_text: str | None = None
    for i, (prompt, candidate_alt) in enumerate(prompts):
        log.info("Image prompt %d/%d: %s", i + 1, len(prompts), prompt[:120])
        try:
            image_bytes = generate_image(prompt=prompt, model_id=image_model)
            alt_text = candidate_alt
            break
        except ImageFilteredError as e:
            log.warning("Image prompt %d/%d filtered -- trying next: %s", i + 1, len(prompts), e)
            continue

    if image_bytes is None:
        raise RuntimeError(f"All {len(prompts)} image prompts filtered by Stability")

    if dry_run:
        save_preview([image_bytes], caption, alt_texts=[alt_text])
        return None

    image_url = upload_image(image_bytes)
    location_id = resolve_location_id(caption_data.get("location_query") or "")
    return publish_image_post(
        image_url=image_url,
        caption=caption,
        location_id=location_id,
        alt_text=alt_text,
        before_publish=before_publish,
    )
