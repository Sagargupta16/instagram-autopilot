"""Generate a video, bake royalty-free audio, publish as Reel.

Fallback chain when anything in the video pipeline fails, in order:
1. S3_VIDEO_BUCKET unset -> post_carousel
2. Luma generation fails -> post_carousel
3. Video download from S3 fails (403 / private bucket) -> post_carousel
4. Audio bake fails (ffmpeg missing, empty manifest, ffmpeg error) -> post_carousel

We fall back to post_carousel (not "publish silent reel with same broken URL")
because handing Meta an unreachable URL always breaks the post. Cloudinary
carousel is the proven publish path and keeps all 5 slide prompts (post_image
would use only the first prompt, wasting the LLM's 5-slide story).

"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import requests

from src.adapters.cloudinary_host import upload_video
from src.adapters.places import resolve_location_id
from src.flows.carousel_flow import post_carousel
from src.media import audio_bake, audio_picker
from src.media.video import generate_video
from src.publishing.reel import publish_reel
from src.settings import settings

log = logging.getLogger(__name__)


class ReelPipelineError(Exception):
    """Any failure between Luma output and Cloudinary-hosted baked mp4."""


def _s3_uri_to_https(s3_uri: str) -> str:
    """Convert s3://bucket/key -> https://bucket.s3.amazonaws.com/key."""
    if not s3_uri.startswith("s3://"):
        return s3_uri
    _, _, rest = s3_uri.partition("s3://")
    bucket, _, key = rest.partition("/")
    return f"https://{bucket}.s3.amazonaws.com/{key}"


def _bake_and_reupload(video_url: str, theme: str, duration_s: int) -> str:
    """Download mp4 via https, bake audio, upload to Cloudinary, return URL.

    Raises ReelPipelineError on any failure so callers fall back cleanly.
    """
    try:
        with tempfile.TemporaryDirectory() as td:
            local_in = Path(td) / "in.mp4"
            resp = requests.get(video_url, timeout=120)
            resp.raise_for_status()
            local_in.write_bytes(resp.content)
            track = audio_picker.pick(theme)
            baked = audio_bake.bake(local_in, track, duration_s)
            return upload_video(baked.read_bytes())
    except (
        audio_bake.AudioBakeError,
        audio_picker.NoTrackAvailableError,
        requests.RequestException,
    ) as e:
        raise ReelPipelineError(str(e)) from e


def post_reel(
    caption_data: dict[str, Any],
    caption: str,
    image_model: str,
    video_model: str,
    *,
    dry_run: bool,
) -> None:
    """Generate video via Luma Ray 2, bake audio, publish as Reel.

    Falls back to post_image on any failure -- handing Meta a URL it
    cannot fetch always breaks the post, so we degrade to the proven
    Cloudinary image path instead.
    """
    video_prompt = caption_data["video_prompt"]
    log.info("Video prompt: %s", video_prompt)

    if not settings.s3_video_bucket:
        log.warning("S3_VIDEO_BUCKET not set -- falling back to carousel post")
        post_carousel(caption_data, caption, image_model, dry_run=dry_run)
        return

    duration_s = 5
    try:
        video_s3_uri = generate_video(
            prompt=video_prompt,
            model_id=video_model,
            s3_output_uri=settings.s3_video_bucket,
            duration_seconds=duration_s,
        )
    except Exception as e:
        log.warning("Luma generation failed (%s) -- falling back to carousel post", e)
        post_carousel(caption_data, caption, image_model, dry_run=dry_run)
        return

    video_https = _s3_uri_to_https(video_s3_uri)
    theme = caption_data.get("audio_theme") or "cinematic"
    try:
        baked_url = _bake_and_reupload(video_https, theme, duration_s)
    except ReelPipelineError as e:
        log.warning(
            "Reel pipeline failed (%s) -- falling back to carousel post to avoid publishing a broken URL",
            e,
        )
        post_carousel(caption_data, caption, image_model, dry_run=dry_run)
        return

    log.info("Baked audio, uploaded to Cloudinary: %s", baked_url)

    if dry_run:
        log.info("DRY RUN: Reel at %s", baked_url)
        return

    location_id = resolve_location_id(caption_data.get("location_query") or "")
    publish_reel(video_url=baked_url, caption=caption, location_id=location_id)
