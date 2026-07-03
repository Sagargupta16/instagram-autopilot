"""Bake a royalty-free audio track into a Luma-generated mp4 via ffmpeg.

Uses stream-copy on the video (preserves Luma pixels bit-for-bit) and
transcodes audio to AAC-LC 48kHz 128kbps stereo -- matches Instagram's
Reels spec so Meta doesn't server-side re-encode. Applies 0.5s
audio fade-in and fade-out; -shortest trims audio to video length;
+faststart moves the moov atom to the front for streaming.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class AudioBakeError(Exception):
    """Raised when ffmpeg is missing or fails."""


def bake(video: Path, track: Path, duration_s: int) -> Path:
    """Return path to `{video.stem}-baked.mp4` with `track` mixed in."""
    if shutil.which("ffmpeg") is None:
        raise AudioBakeError("ffmpeg not on PATH -- install with apt-get install -y ffmpeg")
    output = video.parent / f"{video.stem}-baked.mp4"
    fade_out_start = max(0.0, duration_s - 0.5)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video),
        "-i",
        str(track),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-af",
        f"afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out_start}:d=0.5",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ]
    log.info("ffmpeg bake: %s + %s -> %s", video.name, track.name, output.name)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0:
        raise AudioBakeError(f"ffmpeg failed (rc={result.returncode}): {result.stderr[-500:]}")
    return output
