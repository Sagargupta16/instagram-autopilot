"""Generate a video, bake royalty-free audio, publish as Reel.

Falls back to image_flow if S3_VIDEO_BUCKET is unset. If audio-bake
fails (ffmpeg missing, no track for theme, S3 copy fails), publishes
the original silent reel -- one slot's audio hiccup shouldn't kill the
post entirely.

The bake cycle uses `aws s3 cp` (workflow already has AWS creds for
Luma output) instead of pulling boto3 into the runtime.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.adapters.places import resolve_location_id
from src.flows.image_flow import post_image
from src.media import audio_bake, audio_picker
from src.media.video import generate_video
from src.publishing.reel import publish_reel
from src.settings import settings

log = logging.getLogger(__name__)


def _s3_cp(src: str, dst: str) -> None:
    subprocess.run(["aws", "s3", "cp", src, dst], check=True, capture_output=True, timeout=180)


def _bake_audio_into_s3_mp4(s3_uri: str, theme: str, duration_s: int) -> str:
    """Download from S3, bake audio, re-upload, return new S3 URI."""
    with tempfile.TemporaryDirectory() as td:
        local_in = Path(td) / "in.mp4"
        _s3_cp(s3_uri, str(local_in))
        track = audio_picker.pick(theme)
        baked = audio_bake.bake(local_in, track, duration_s)
        baked_uri = s3_uri.replace("/output.mp4", "/baked.mp4")
        _s3_cp(str(baked), baked_uri)
        return baked_uri


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

    final_uri = video_s3_uri
    theme = caption_data.get("audio_theme") or "cinematic"
    try:
        final_uri = _bake_audio_into_s3_mp4(video_s3_uri, theme, duration_s)
        log.info("Baked audio into reel: %s", final_uri)
    except (audio_bake.AudioBakeError, audio_picker.NoTrackAvailableError) as e:
        log.warning("Audio bake failed (%s) -- publishing silent reel", e)
    except subprocess.CalledProcessError as e:
        log.warning("S3 copy failed (%s) -- publishing original", e)

    if dry_run:
        log.info("DRY RUN: Reel at %s", final_uri)
        return

    location_id = resolve_location_id(caption_data.get("location_query") or "")
    publish_reel(video_url=final_uri, caption=caption, location_id=location_id)
