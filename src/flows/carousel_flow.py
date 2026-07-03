"""Generate N AI images and publish as an Instagram carousel.

Content-filtered slides are skipped (Stability blocks ~1-2% of prompts
that mention specific ethnicities, occupations, or ambiguous framing).
If we get at least 2 slides out of the requested 5, we still publish --
IG's carousel accepts 2-10 items. Below 2, we surface the failure.
"""

from __future__ import annotations

import logging
from typing import Any

from src.adapters.cloudinary_host import upload_image
from src.adapters.places import resolve_location_id
from src.media.image import ImageFilteredError, generate_image
from src.publishing.carousel import publish_carousel

log = logging.getLogger(__name__)

# IG carousel spec: 2 min, 10 max slides.
MIN_CAROUSEL_SLIDES = 2


def post_carousel(
    caption_data: dict[str, Any], caption: str, image_model: str, *, dry_run: bool
) -> None:
    """Generate each slide's image, upload, and publish as a carousel."""
    image_prompts: list[str] = caption_data["image_prompts"]
    image_urls: list[str] = []

    for i, prompt in enumerate(image_prompts):
        log.info("Slide %d/%d prompt: %s", i + 1, len(image_prompts), prompt[:120])
        try:
            image_bytes = generate_image(prompt=prompt, model_id=image_model)
        except ImageFilteredError as e:
            log.warning("Slide %d/%d filtered -- skipping: %s", i + 1, len(image_prompts), e)
            continue
        log.info("Slide %d: %d bytes", i + 1, len(image_bytes))
        if not dry_run:
            image_urls.append(upload_image(image_bytes))

    if dry_run:
        log.info("DRY RUN: Generated %d carousel slides", len(image_prompts))
        return

    if len(image_urls) < MIN_CAROUSEL_SLIDES:
        raise RuntimeError(
            f"Only {len(image_urls)} slides survived filtering (need >= {MIN_CAROUSEL_SLIDES}); "
            "IG carousel would reject. Slot skipped."
        )

    location_id = resolve_location_id(caption_data.get("location_query") or "")
    publish_carousel(image_urls=image_urls, caption=caption, location_id=location_id)
