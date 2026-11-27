"""Check a rendered Reel MP4 with ffprobe before it is uploaded."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.media.video.svg_video import FPS, HEIGHT, WIDTH, SvgVideoError

MAX_BYTES = 100_000_000


PROBE = "format=duration,size:stream=codec_type,codec_name,profile,width,height,pix_fmt,"
PROBE += "avg_frame_rate,sample_rate,channels"


class SpecMismatch(SvgVideoError):
    """The video's own bytes fail the check: they do not match the Reel spec, or ffprobe
    rejected them (an exit code above 0, from an ffprobe whose `-version` runs). A missing ffprobe,
    one that does not run at all, a timeout, unreadable output and a killed ffprobe (a negative
    return code) stay plain SvgVideoError: not the file's fault."""


def _ffprobe_runs() -> bool:
    """Whether ffprobe itself works here: a broken install exits above 0 on every file, and
    that must never make a good video look bad."""
    command = ["ffprobe", "-version"]
    try:
        done = subprocess.run(command, capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def probe(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-show_entries", PROBE, "-of", "json", str(path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=True)
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        rejected = isinstance(error, subprocess.CalledProcessError) and error.returncode > 0
        kind = SpecMismatch if rejected and _ffprobe_runs() else SvgVideoError
        raise kind(f"ffprobe could not read the video: {type(error).__name__}") from error


def verify(path: Path, duration: float, *, audio: bool) -> dict:
    """Check the delivered MP4 against the Reel spec; returns a short summary."""
    info = probe(path)
    streams = info.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    sound = [s for s in streams if s.get("codec_type") == "audio"]
    summary = {
        "duration": float(info.get("format", {}).get("duration", 0)),
        "bytes": int(info.get("format", {}).get("size", 0)),
        "video": video[0] if video else {},
        "audio": sound[0] if sound else None,
    }
    v = summary["video"]
    problems = [
        message
        for failed, message in (
            (len(video) != 1, "exactly one video stream"),
            (v.get("codec_name") != "h264" or v.get("profile") != "High", "H.264 High profile"),
            ((v.get("width"), v.get("height")) != (WIDTH, HEIGHT), f"{WIDTH}x{HEIGHT}"),
            (v.get("pix_fmt") != "yuv420p", "yuv420p"),
            (v.get("avg_frame_rate") != f"{FPS}/1", f"{FPS} fps"),
            (abs(summary["duration"] - duration) > 0.25, f"about {duration:.1f} s"),
            (not 0 < summary["bytes"] <= MAX_BYTES, "a size below 100 MB"),
            (audio and (len(sound) != 1 or sound[0].get("codec_name") != "aac"), "AAC audio"),
            (not audio and bool(sound), "no audio stream"),
        )
        if failed
    ]
    if problems:
        raise SpecMismatch("rendered video does not match the Reel spec: " + ", ".join(problems))
    return summary
