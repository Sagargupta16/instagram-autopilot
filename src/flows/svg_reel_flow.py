"""Animated SVG Reels rendered locally. The account publishes SVG Reels only: a failure before
the publisher boundary skips the post (SvgReelError) and never falls back to a photo format.

Order: attribution and audio checks, then rendering, then ffprobe validation of the delivered
MP4, then upload. The publisher boundary, callback and receipt rules match the Luma Reel path.
The visual look comes from caption_data["look"] (the post rotation) and the cover frame is the
composer's moment of the complete scene, sent as thumb_offset.
"""

from __future__ import annotations

import json
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.adapters.cloudinary_host import upload_video
from src.content.scenes import source_line
from src.content.sources import publication_name
from src.flows.previews import save_preview
from src.flows.reel_flow import select_audio
from src.media import audio_bake, audio_picker, reel_probe, svg_video
from src.media.audio_manifest import AudioTrack
from src.media.reel_svg import LayoutError, Reel, compose
from src.publishing.reel import publish_reel

log = logging.getLogger(__name__)

# Local failures whose messages carry no credentials and are worth reporting in full.
KNOWN = (
    svg_video.SvgVideoError,
    LayoutError,
    audio_bake.AudioBakeError,
    audio_picker.NoTrackAvailableError,
)


class SvgReelError(Exception):
    """The Reel could not be prepared; nothing was uploaded or published."""


def credited(caption: str, scene: dict[str, Any], sources: list[dict]) -> str:
    """Add the adapter-named source to the caption when the scene shows a stat."""
    if scene["kind"] != "stat":
        return caption
    record = sources[scene["source_index"]]
    line = f"Source: {publication_name(record)}"
    if record.get("url") and record["url"] not in caption:
        line += f" {record['url']}"
    return caption if line in caption else f"{caption}\n\n{line}"


def _render(svg: str, duration: float, track: AudioTrack | None) -> bytes:
    with tempfile.TemporaryDirectory(prefix="svg-reel-") as temporary:
        video = svg_video.render(svg, duration, Path(temporary) / "reel.mp4")
        if track:
            video = audio_bake.bake(video, track.path, duration)
        summary = reel_probe.verify(video, duration, audio=track is not None)
        log.info("SVG Reel ready: %.1f s, %d bytes", summary["duration"], summary["bytes"])
        return video.read_bytes()


def _prepare(
    caption_data: dict[str, Any], caption: str, audio_theme: str | None
) -> tuple[str, Reel, bytes, AudioTrack | None]:
    """Caption, composed Reel, verified MP4 bytes and the audio track, or an exception."""
    sources = caption_data.get("sources") or []
    scene = caption_data.get("scene")
    if not isinstance(scene, dict):
        raise SvgReelError("validated scene is missing")
    reel_caption = credited(caption, scene, sources)
    track = select_audio(audio_theme or caption_data.get("audio_theme") or "chill")
    if track and track.attribution:
        reel_caption = f"{reel_caption}\n\n{track.attribution}"
    if len(reel_caption) > 2200:
        raise SvgReelError("Source or audio attribution exceeds the caption limit")
    browser = svg_video.ensure_available()
    look = caption_data.get("look", 0)
    reel = compose(scene, source_line=source_line(scene, sources), look=look)
    log.info("Rendering %s SVG Reel (%.1f s) with %s", scene["kind"], reel.duration, browser)
    return reel_caption, reel, _render(reel.svg, reel.duration, track), track


def post_svg_reel(
    caption_data: dict[str, Any],
    caption: str,
    *,
    dry_run: bool,
    before_publish: Callable[[str], None] | None = None,
    audio_theme: str | None = None,
) -> str | None:
    """Return the media ID, or None for a saved preview; never retry publishing."""
    try:
        reel_caption, reel, video_bytes, track = _prepare(caption_data, caption, audio_theme)
        if dry_run:
            folder = save_preview([video_bytes], reel_caption, suffix="mp4")
            (folder / "reel.svg").write_text(reel.svg, encoding="utf-8")
            evidence = {
                "scene": caption_data["scene"],
                "sources": caption_data.get("sources"),
                "look": caption_data.get("look", 0),
                "thumb_offset_ms": reel.thumb_offset_ms,
            }
            (folder / "scene.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return None
        video_url = upload_video(video_bytes)
    except Exception as error:
        # This scope excludes every publisher and callback operation, as in the Luma path.
        own = isinstance(error, (SvgReelError, *KNOWN))
        detail = f"{type(error).__name__}: {error}" if own else type(error).__name__
        log.error("SVG Reel skipped before publishing (%s); nothing was posted", detail)
        raise SvgReelError(f"SVG Reel skipped before publishing: {detail}") from error

    media_id = publish_reel(
        video_url=video_url,
        caption=reel_caption,
        before_publish=before_publish,
        thumb_offset=reel.thumb_offset_ms,
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
