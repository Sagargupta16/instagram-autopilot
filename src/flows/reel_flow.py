"""Generate an AI video and publish as an Instagram Reel.

Falls back to image_flow if S3_VIDEO_BUCKET is unset (Nova Reel requires S3).
"""

from __future__ import annotations

import logging
from typing import Any

from src.flows.image_flow import post_image
from src.media.video import generate_video
from src.publishing.reel import publish_reel
from src.settings import settings

log = logging.getLogger(__name__)


def post_reel(
    caption_data: dict[str, Any],
    caption: str,
    image_model: str,
    video_model: str,
    *,
    dry_run: bool,
) -> None:
    """Generate video via Nova Reel and publish as Reel, or fall back to image."""
    video_prompt = caption_data["video_prompt"]
    log.info("Video prompt: %s", video_prompt)

    if not settings.s3_video_bucket:
        log.warning("S3_VIDEO_BUCKET not set -- falling back to image post")
        post_image(caption_data, caption, image_model, dry_run=dry_run)
        return

    video_s3_uri = generate_video(
        prompt=video_prompt,
        model_id=video_model,
        s3_output_uri=settings.s3_video_bucket,
    )

    if dry_run:
        log.info("DRY RUN: Video at %s", video_s3_uri)
        return

    publish_reel(video_url=video_s3_uri, caption=caption)
