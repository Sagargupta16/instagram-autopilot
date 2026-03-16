"""Stitch images + audio into Reels video using ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def create_reel(
    background_image: Path,
    audio: Path,
    output_filename: str = "reel.mp4",
    subtitle_text: str | None = None,
) -> Path:
    """Create a Reel video from a background image + voiceover audio.

    ffmpeg loops the image for the duration of the audio and overlays
    burned-in subtitles if provided.
    """
    output_path = OUTPUT_DIR / output_filename

    # Base command: loop image for audio duration
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-loop", "1",
        "-i", str(background_image),
        "-i", str(audio),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",  # Stop when audio ends
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
    ]

    # Add subtitle overlay if provided
    if subtitle_text:
        srt_path = _create_srt(subtitle_text)
        cmd[-1] += f",subtitles={str(srt_path).replace(chr(92), '/')}:force_style='FontSize=22,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2,MarginV=80'"

    cmd.append(str(output_path))

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return output_path


def create_slideshow_reel(
    images: list[Path],
    audio: Path,
    seconds_per_slide: float = 3.0,
    output_filename: str = "slideshow_reel.mp4",
) -> Path:
    """Create a Reel from multiple images (slideshow style) + audio."""
    output_path = OUTPUT_DIR / output_filename

    # Create concat file for ffmpeg
    concat_file = OUTPUT_DIR / "concat.txt"
    lines = [f"file '{img}'\nduration {seconds_per_slide}" for img in images]
    # Repeat last image to avoid ffmpeg cut
    lines.append(f"file '{images[-1]}'")
    concat_file.write_text("\n".join(lines))

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-i", str(audio),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return output_path


def _create_srt(text: str, words_per_segment: int = 6) -> Path:
    """Create a basic SRT subtitle file from text."""
    srt_path = OUTPUT_DIR / "subtitles.srt"
    words = text.split()
    segments = [
        " ".join(words[i : i + words_per_segment])
        for i in range(0, len(words), words_per_segment)
    ]

    srt_lines: list[str] = []
    seconds_per_segment = 2.5
    for i, segment in enumerate(segments):
        start = i * seconds_per_segment
        end = start + seconds_per_segment
        srt_lines.append(str(i + 1))
        srt_lines.append(f"{_format_time(start)} --> {_format_time(end)}")
        srt_lines.append(segment)
        srt_lines.append("")

    srt_path.write_text("\n".join(srt_lines))
    return srt_path


def _format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
