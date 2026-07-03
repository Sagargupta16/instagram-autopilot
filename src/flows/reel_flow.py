"""Generate a video, bake royalty-free audio, publish as Reel.

Falls back to image_flow if S3_VIDEO_BUCKET is unset. If audio-bake
fails (ffmpeg missing, no track for theme, download fails), publishes
the original silent reel -- one slot's audio hiccup shouldn't kill the
post entirely.

We fetch the Luma mp4 via https (the S3 URI is converted; bucket must
already be readable, which it must be for IG to fetch it too), bake
with ffmpeg locally, then upload the baked mp4 to Cloudinary. No new
AWS creds needed at runtime.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import requests

from src.adapters.cloudinary_host import upload_video
from src.adapters.places import resolve_location_id
from src.flows.image_flow import post_image
from src.media import audio_bake, audio_picker
from src.media.video import generate_video
from src.publishing.reel import publish_reel
from src.settings import settings

log = logging.getLogger(__name__)


def _s3_uri_to_https(s3_uri: str) -> str:
    """Convert s3://bucket/key -> https://bucket.s3.amazonaws.com/key."""
    if not s3_uri.startswith("s3://"):
        return s3_uri
    _, _, rest = s3_uri.partition("s3://")
    bucket, _, key = rest.partition("/")
    return f"https://{bucket}.s3.amazonaws.com/{key}"


def _bake_and_reupload(video_url: str, theme: str, duration_s: int) -> str:
    """Download mp4 via https, bake audio, upload to Cloudinary, return URL."""
    with tempfile.TemporaryDirectory() as td:
        local_in = Path(td) / "in.mp4"
        resp = requests.get(video_url, timeout=120, stream=True)
        resp.raise_for_status()
        local_in.write_bytes(resp.content)
        track = audio_picker.pick(theme)
        baked = audio_bake.bake(local_in, track, duration_s)
        return upload_video(baked.read_bytes())


def post_reel(
    caption_data: dict[str, Any],
    caption: str,
    image_model: str,
    video_model: str,
    *,
    dry_run: bool,
) -> None:
    """Generate video via Luma Ray 2, bake audio, publish as Reel."""
    video_prompt = caption_data["video_prompt"]
    log.info("Video prompt: %s", video_prompt)

    if not settings.s3_video_bucket:
        log.warning("S3_VIDEO_BUCKET not set -- falling back to image post")
        post_image(caption_data, caption, image_model, dry_run=dry_run)
        return

    duration_s = 5
    video_s3_uri = generate_video(
        prompt=video_prompt,
        model_id=video_model,
        s3_output_uri=settings.s3_video_bucket,
        duration_seconds=duration_s,
    )
    video_https = _s3_uri_to_https(video_s3_uri)

    final_url = video_https
    theme = caption_data.get("audio_theme") or "cinematic"
    try:
        final_url = _bake_and_reupload(video_https, theme, duration_s)
        log.info("Baked audio, uploaded to Cloudinary: %s", final_url)
    except (audio_bake.AudioBakeError, audio_picker.NoTrackAvailableError) as e:
        log.warning("Audio bake failed (%s) -- publishing silent reel", e)
    except requests.RequestException as e:
        log.warning("Video download failed (%s) -- publishing original URI", e)

    if dry_run:
        log.info("DRY RUN: Reel at %s", final_url)
        return

    location_id = resolve_location_id(caption_data.get("location_query") or "")
    publish_reel(video_url=final_url, caption=caption, location_id=location_id)
