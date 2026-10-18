"""Bake a royalty-free audio track into a Luma-generated mp4 via ffmpeg.

Uses stream-copy on the video (preserves Luma pixels bit-for-bit) and
transcodes audio to AAC-LC 48kHz 128kbps stereo -- matches Instagram's
Reels spec so Meta doesn't server-side re-encode. Applies 0.5s
audio fade-in and a fade-out that ends at the video's real (fractional)
duration; -shortest trims audio to video length; +faststart moves the
moov atom to the front for streaming. `mix` does the same for an SVG Reel with narration:
each voice clip starts at its beat and the music dips under the voice (sidechain ducking).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class AudioBakeError(Exception):
    """Raised when ffmpeg is missing or fails."""


def ensure_available() -> None:
    """Check local prerequisites before paid video generation."""
    if shutil.which("ffmpeg") is None:
        raise AudioBakeError("ffmpeg not on PATH -- install with apt-get install -y ffmpeg")


def bake(video: Path, track: Path, duration_s: float) -> Path:
    """Return path to `{video.stem}-baked.mp4` with `track` mixed in."""
    ensure_available()
    output = video.parent / f"{video.stem}-baked.mp4"
    fade_out_start = f"{max(0.0, duration_s - 0.5):.3f}".rstrip("0").rstrip(".") or "0"
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
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except subprocess.TimeoutExpired as error:
        raise AudioBakeError("ffmpeg timed out after 120 seconds") from error
    except OSError as error:
        raise AudioBakeError("ffmpeg could not start") from error
    if result.returncode != 0:
        raise AudioBakeError(f"ffmpeg failed (rc={result.returncode}): {result.stderr[-500:]}")
    return output


# Speech normalized for phones (-16 LUFS integrated, -1.5 dBTP), the music bed a step below
# it and ducked further under every spoken line.
VOICE_LOUDNESS = "loudnorm=I=-16:TP=-1.5:LRA=11"
MUSIC_UNDER_VOICE = 0.5
STEREO = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"


def mix_graph(
    starts: list[float], duration_s: float, *, music: bool, fade: str, music_volume: float
) -> str:
    """The filter graph: delayed voice clips, padded to the Reel, over the ducked music."""
    first = 2 if music else 1
    chains = [
        f"[{first + index}:a]{STEREO},adelay={round(start * 1000)}:all=1[v{index}]"
        for index, start in enumerate(starts)
    ]
    voices = "".join(f"[v{index}]" for index in range(len(starts)))
    chains.append(
        f"{voices}amix=inputs={len(starts)}:normalize=0:duration=longest,{VOICE_LOUDNESS},"
        f"{STEREO},apad=whole_dur={duration_s:.3f}[voice]"
    )
    if not music:
        return ";".join([*chains, f"[voice]{fade},alimiter=limit=0.95[out]"])
    return ";".join(
        [
            *chains,
            f"[1:a]{STEREO},volume={music_volume}[bed]",
            "[voice]asplit=2[spoken][key]",
            "[bed][key]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=400[ducked]",
            f"[ducked][spoken]amix=inputs=2:normalize=0:duration=first,{fade},"
            "alimiter=limit=0.95[out]",
        ]
    )


def mix(
    video: Path,
    duration_s: float,
    *,
    voice: list[tuple[Path, float]],
    music: Path | None = None,
    music_volume: float = MUSIC_UNDER_VOICE,
) -> Path:
    """Return `{video.stem}-mixed.mp4`: each (clip, start seconds) over the optional music."""
    ensure_available()
    output = video.parent / f"{video.stem}-mixed.mp4"
    fade_out_start = f"{max(0.0, duration_s - 0.5):.3f}".rstrip("0").rstrip(".") or "0"
    fade = f"afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out_start}:d=0.5"
    inputs = ["-i", str(video)]
    for path in [*([music] if music else []), *(clip for clip, _ in voice)]:
        inputs += ["-i", str(path)]
    graph = mix_graph(
        [start for _, start in voice],
        duration_s,
        music=music is not None,
        fade=fade,
        music_volume=music_volume,
    )
    cmd = [
        *("ffmpeg", "-y", *inputs, "-filter_complex", graph, "-map", "0:v:0", "-map", "[out]"),
        *("-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"),
        *("-t", f"{duration_s:.3f}", "-movflags", "+faststart", str(output)),
    ]
    log.info("ffmpeg mix: %s + %d voice clips -> %s", video.name, len(voice), output.name)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as error:
        raise AudioBakeError("ffmpeg timed out after 180 seconds") from error
    except OSError as error:
        raise AudioBakeError("ffmpeg could not start") from error
    if result.returncode != 0:
        raise AudioBakeError(f"ffmpeg mix failed (rc={result.returncode}): {result.stderr[-500:]}")
    return output
