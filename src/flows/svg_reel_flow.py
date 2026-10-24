"""Animated SVG Reels rendered locally. The account publishes SVG Reels only: a failure before
the publisher boundary skips the post (SvgReelError) and never falls back to a photo format.

Order: attribution and audio checks, then the optional narration (a local voice reading the
scene's own words; any failure leaves the Reel music-only), then rendering paced to the
narration, then ffprobe validation of the delivered MP4, then upload. The publisher boundary,
callback and receipt rules match the Luma Reel path.
The visual look comes from caption_data["look"] (the post rotation), the end card's handle from
a live read of the connected account, and the cover frame is the composer's moment of the
complete scene, sent as thumb_offset.
"""

from __future__ import annotations

import json
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from src.adapters.cloudinary_host import upload_video
from src.content.scenes import source_line
from src.content.sources import publication_name
from src.flows.previews import save_preview
from src.flows.reel_flow import select_audio
from src.media import audio_bake, audio_picker, narration, reel_probe, svg_video
from src.media.audio_manifest import AudioTrack
from src.media.reel_svg import LayoutError, Reel, compose, length
from src.publishing.account import handle as account_handle
from src.publishing.reel import publish_reel
from src.settings import settings

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
    url = record.get("url") or ""
    # Google News RSS links are long opaque redirects, not the article: name the publisher only.
    if url and urlsplit(url).hostname != "news.google.com" and url not in caption:
        line += f" {url}"
    return caption if line in caption else f"{caption}\n\n{line}"


def _voiced(
    video: Path, reel: Reel, voice: narration.Narration, track: AudioTrack | None
) -> Path | None:
    """The narrated mix, or None (logged) so the caller falls back to the music-only bake."""
    starts = [beat + narration.LEAD_S for beat in reel.beats]
    clips = list(zip(voice.clips, starts, strict=True))
    try:
        return audio_bake.mix(
            video, reel.duration, voice=clips, music=track.path if track else None
        )
    except audio_bake.AudioBakeError as error:
        log.warning("SVG Reel without narration (%s)", error)
        return None


def _render(
    reel: Reel, track: AudioTrack | None, voice: narration.Narration | None, workdir: Path
) -> tuple[bytes, bool]:
    """Verified MP4 bytes and whether the narration made it into the audio."""
    video = svg_video.render(reel.svg, reel.duration, workdir / "reel.mp4")
    mixed = _voiced(video, reel, voice, track) if voice else None
    if mixed:
        video = mixed
    elif track:
        video = audio_bake.bake(video, track.path, reel.duration)
    summary = reel_probe.verify(video, reel.duration, audio=bool(track or mixed))
    log.info("SVG Reel ready: %.1f s, %d bytes", summary["duration"], summary["bytes"])
    return video.read_bytes(), mixed is not None


def _prepare(
    caption_data: dict[str, Any], caption: str, audio_theme: str | None
) -> tuple[str, Reel, bytes, AudioTrack | None, tuple[str, ...]]:
    """Caption, composed Reel, verified MP4 bytes, the audio track and the spoken lines."""
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
    with tempfile.TemporaryDirectory(prefix="svg-reel-") as temporary:
        workdir = Path(temporary)
        voice = None
        if settings.narration:
            voice = narration.fitted(
                scene, workdir, lambda pace: length(scene, pace), voice=settings.narration_voice
            )
        else:
            log.info("SVG Reel without narration: narration is off (NARRATION=false)")
        if voice and len(f"{reel_caption}\n\n{narration.CREDIT}") > 2200:
            log.warning("SVG Reel without narration: its credit would exceed the caption limit")
            voice = None
        reel = compose(
            scene,
            source_line=source_line(scene, sources),
            look=look,
            pace=voice.pace if voice else (),
            handle=account_handle(),
        )
        log.info("Rendering %s SVG Reel (%.1f s) with %s", scene["kind"], reel.duration, browser)
        video, narrated = _render(reel, track, voice, workdir)
    if narrated:
        reel_caption = f"{reel_caption}\n\n{narration.CREDIT}"
    return reel_caption, reel, video, track, voice.lines if narrated else ()


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
        reel_caption, reel, video_bytes, track, spoken = _prepare(
            caption_data, caption, audio_theme
        )
        if dry_run:
            folder = save_preview([video_bytes], reel_caption, suffix="mp4")
            (folder / "reel.svg").write_text(reel.svg, encoding="utf-8")
            evidence = {
                "scene": caption_data["scene"],
                "sources": caption_data.get("sources"),
                "look": caption_data.get("look", 0),
                "thumb_offset_ms": reel.thumb_offset_ms,
                **({"narration": list(spoken)} if spoken else {}),
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
