"""Prepare Reels with local audio; fallback ends before the publisher boundary."""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.adapters.cloudinary_host import upload_video
from src.adapters.places import resolve_location_id
from src.flows.carousel_flow import post_carousel
from src.flows.previews import save_preview
from src.media import audio_bake, audio_picker
from src.media.audio_manifest import AudioTrack
from src.media.video import download_video, generate_video
from src.publishing.reel import publish_reel
from src.settings import settings

log = logging.getLogger(__name__)


class ReelPipelineError(Exception):
    """A failure before the publisher has been called."""


def _select_audio(theme: str) -> AudioTrack | None:
    try:
        track = audio_picker.select(theme)
        audio_bake.ensure_available()
        return track
    except (audio_picker.NoTrackAvailableError, audio_bake.AudioBakeError):
        if getattr(settings, "allow_silent_reels", False) is True:
            log.info("Silent Reel explicitly enabled; continuing without audio")
            return None
        raise


def _prepare_video(prompt: str, model: str, track: AudioTrack | None) -> bytes:
    uri = generate_video(
        prompt=prompt, model_id=model, s3_output_uri=settings.s3_video_bucket, duration_seconds=5
    )
    with tempfile.TemporaryDirectory() as temporary:
        local = Path(temporary) / "in.mp4"
        download_video(uri, local)
        output = audio_bake.bake(local, track.path, 5) if track else local
        return output.read_bytes()


def post_reel(
    caption_data: dict[str, Any],
    caption: str,
    image_model: str,
    video_model: str,
    *,
    dry_run: bool,
    before_publish: Callable[[str], None] | None = None,
) -> str | None:
    """Return the media ID, or None for a generated preview; never retry publishing."""
    try:
        if not settings.s3_video_bucket:
            raise ReelPipelineError("S3 output bucket is not configured")
        track = _select_audio(caption_data.get("audio_theme") or "cinematic")
        reel_caption = caption
        if track and track.attribution:
            reel_caption = f"{caption}\n\n{track.attribution}"
            if len(reel_caption) > 2200:
                raise ReelPipelineError("Audio attribution exceeds caption limit")
        video_bytes = _prepare_video(caption_data["video_prompt"], video_model, track)
        if dry_run:
            save_preview([video_bytes], reel_caption, suffix="mp4")
            return None
        video_url = upload_video(video_bytes)
    except Exception as error:
        # SDKs expose several unrelated error hierarchies. This scope deliberately
        # excludes ALL publisher/callback operations, including ambiguous failures.
        log.warning("Reel preparation failed (%s); falling back to carousel", type(error).__name__)
        return post_carousel(
            caption_data, caption, image_model, dry_run=dry_run, before_publish=before_publish
        )

    location_id = resolve_location_id(caption_data.get("location_query") or "")
    media_id = publish_reel(
        video_url=video_url,
        caption=reel_caption,
        location_id=location_id,
        before_publish=before_publish,
    )
    if track:
        try:
            audio_picker.record_usage(track)
        except Exception as error:
            # A secondary cache failure must not discard a confirmed publication receipt.
            log.warning(
                "Reel %s published, but audio history could not be saved (%s)",
                media_id,
                type(error).__name__,
            )
    return media_id
