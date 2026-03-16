"""Generate text-to-speech audio using edge-tts (free, no API key needed)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Good voices for content narration
VOICES = {
    "male_us": "en-US-GuyNeural",
    "female_us": "en-US-JennyNeural",
    "male_uk": "en-GB-RyanNeural",
    "female_uk": "en-GB-SoniaNeural",
}

DEFAULT_VOICE = VOICES["male_us"]


async def _generate_audio(text: str, voice: str, output_path: Path) -> Path:
    communicate = edge_tts.Communicate(text, voice, rate="-5%")
    await communicate.save(str(output_path))
    return output_path


def generate_voiceover(
    text: str,
    filename: str = "voiceover.mp3",
    voice: str = DEFAULT_VOICE,
) -> Path:
    """Generate voiceover audio from text. Returns path to MP3 file."""
    output_path = OUTPUT_DIR / filename
    asyncio.run(_generate_audio(text, voice, output_path))
    return output_path


async def _generate_subtitle_data(text: str, voice: str) -> list[dict]:
    """Generate audio with word-level timing for subtitle generation."""
    subtitles: list[dict] = []
    communicate = edge_tts.Communicate(text, voice, rate="-5%")

    async for chunk in communicate.stream():
        if chunk["type"] == "WordBoundary":
            subtitles.append(
                {
                    "text": chunk["text"],
                    "offset_ms": chunk["offset"] // 10000,  # Convert to ms
                    "duration_ms": chunk["duration"] // 10000,
                }
            )
    return subtitles


def generate_voiceover_with_subtitles(
    text: str,
    filename: str = "voiceover.mp3",
    voice: str = DEFAULT_VOICE,
) -> tuple[Path, list[dict]]:
    """Generate voiceover + subtitle timing data. Returns (audio_path, subtitles)."""
    audio_path = generate_voiceover(text, filename, voice)
    subtitles = asyncio.run(_generate_subtitle_data(text, voice))
    return audio_path, subtitles
