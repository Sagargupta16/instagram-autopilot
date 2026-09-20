"""Generate N AI images and publish as an Instagram carousel.

Content-filtered slides are skipped (Stability blocks ~1-2% of prompts
that mention specific ethnicities, occupations, or ambiguous framing).
If we get at least 2 slides out of the requested 5, we still publish --
IG's carousel accepts 2-10 items. Below 2, we surface the failure.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from src.adapters.cloudinary_host import upload_image
from src.adapters.places import resolve_location_id
from src.flows.previews import image_items, save_preview
from src.media.image import ImageFilteredError, generate_image
from src.publishing.carousel import publish_carousel

log = logging.getLogger(__name__)

# IG carousel spec: 2 min, 10 max slides.
MIN_CAROUSEL_SLIDES = 2


def post_carousel(
    caption_data: dict[str, Any],
    caption: str,
    image_model: str,
    *,
    dry_run: bool,
    before_publish: Callable[[str], None] | None = None,
) -> str | None:
    """Generate each slide's image, upload, and publish as a carousel."""
    items = image_items(caption_data)
    images: list[bytes] = []
    surviving_alts: list[str | None] = []

    for i, (prompt, alt_text) in enumerate(items):
        log.info("Slide %d/%d prompt: %s", i + 1, len(items), prompt[:120])
        try:
            image_bytes = generate_image(prompt=prompt, model_id=image_model)
        except ImageFilteredError as e:
            log.warning("Slide %d/%d filtered -- skipping: %s", i + 1, len(items), e)
            continue
        log.info("Slide %d: %d bytes", i + 1, len(image_bytes))
        images.append(image_bytes)
        surviving_alts.append(alt_text)

    if dry_run:
        save_preview(images, caption, alt_texts=surviving_alts)

    if len(images) < MIN_CAROUSEL_SLIDES:
        raise RuntimeError(
            f"Only {len(images)} slides survived filtering (need >= {MIN_CAROUSEL_SLIDES}); "
            "IG carousel would reject. Slot skipped."
        )
    if dry_run:
        return None

    image_urls = [upload_image(image_bytes) for image_bytes in images]
    location_id = resolve_location_id(caption_data.get("location_query") or "")
    return publish_carousel(
        image_urls=image_urls,
        caption=caption,
        location_id=location_id,
        alt_texts=surviving_alts if caption_data.get("alt_texts") else None,
        before_publish=before_publish,
    )
