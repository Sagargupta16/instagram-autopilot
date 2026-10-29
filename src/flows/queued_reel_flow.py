"""Publish a finished Reel from the private queue: download it, check the delivered bytes with
ffprobe against the Reel spec and the entry's own duration (contract 18), upload it, then
publish through the same checkpoint as every other Reel. Nothing here renders or writes text:
the video and its caption arrive finished, with their facts checked when they were made."""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable
from pathlib import Path

from src.adapters.cloudinary_host import upload_video
from src.adapters.reel_queue import QueuedReel, QueueError, ReelQueue
from src.flows.previews import save_preview
from src.media import reel_probe
from src.media.svg_video import SvgVideoError
from src.publishing.reel import publish_reel

log = logging.getLogger(__name__)

# Local failures whose messages carry no credentials and are worth reporting in full.
KNOWN = (SvgVideoError, QueueError)


class QueuedReelError(Exception):
    """The queued video could not be prepared; nothing was uploaded or published."""


def post_queued_reel(
    item: QueuedReel,
    queue: ReelQueue,
    *,
    dry_run: bool,
    before_publish: Callable[[str], None] | None = None,
) -> str | None:
    """Return the media ID, or None for a saved preview; never retry publishing."""
    entry = item.entry
    try:
        with tempfile.TemporaryDirectory(prefix="queued-reel-") as temporary:
            video = queue.video(item, Path(temporary) / "reel.mp4")
            summary = reel_probe.verify(video, entry.duration_s, audio=entry.audio)
            body = video.read_bytes()
        log.info(
            "Queued Reel %s ready: %.1f s, %d bytes", item.slug, summary["duration"], len(body)
        )
        if dry_run:
            save_preview([body], entry.text, suffix="mp4", alt_texts=[entry.alt_text or None])
            return None
        video_url = upload_video(body)
    except Exception as error:
        # This scope excludes every publisher and callback operation, as in the SVG Reel path.
        own = isinstance(error, KNOWN)
        detail = f"{type(error).__name__}: {error}" if own else type(error).__name__
        log.error("Queued Reel %s skipped before publishing (%s)", item.slug, detail)
        raise QueuedReelError(f"Queued Reel skipped before publishing: {detail}") from error

    return publish_reel(
        video_url=video_url,
        caption=entry.text,
        before_publish=before_publish,
        thumb_offset=entry.cover_ms,
    )
