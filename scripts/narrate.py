# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["kokoro-onnx==0.6.1"]
# ///
"""Speak each narration line with the local Kokoro voice and write one WAV per line.

Runs in its own locked environment because kokoro-onnx does not support Python 3.14, which the
publisher uses. src/media/audio/narration.py calls it from a temporary working directory as:
    uv run --frozen --python 3.13 --script scripts/narrate.py < request.json

The request on stdin is {"voice": name, "speed": number, "lines": [text, ...]}; it carries no
paths. The model files are always assets/voice/ beside this script (fetched and checked by
scripts/fetch_voice_model.py), and the output always goes to ./narration in the working
directory: NN.wav per line (mono, 16-bit, the model's 24 kHz) and narration.json with
{"durations": [seconds, ...]} in line order. Nothing is downloaded here.
"""

from __future__ import annotations

import json
import re
import sys
import wave
from pathlib import Path

import numpy as np
from kokoro_onnx import Kokoro

VOICE_DIR = Path(__file__).resolve().parent.parent / "assets" / "voice"
MODEL = VOICE_DIR / "kokoro-v1.0.fp16.onnx"
VOICES = VOICE_DIR / "voices-v1.0.bin"
VOICE_NAME = re.compile(r"[a-z]{2}_[a-z]{2,20}")
MAX_LINES, MAX_CHARS = 12, 400


def checked(request: object) -> tuple[str, float, list[str]]:
    """The voice, speed and lines, or ValueError for anything outside their narrow shapes."""
    if not isinstance(request, dict):
        raise ValueError("the request must be a JSON object")
    voice, speed, lines = request.get("voice"), request.get("speed"), request.get("lines")
    if not isinstance(voice, str) or not VOICE_NAME.fullmatch(voice):
        raise ValueError("voice must be a Kokoro voice name such as af_heart")
    if not isinstance(speed, (int, float)) or isinstance(speed, bool) or not 0.5 <= speed <= 2:
        raise ValueError("speed must be a number from 0.5 to 2")
    if not isinstance(lines, list) or not 1 <= len(lines) <= MAX_LINES:
        raise ValueError(f"lines must be a list of 1 to {MAX_LINES} strings")
    if not all(isinstance(line, str) and 0 < len(line.strip()) <= MAX_CHARS for line in lines):
        raise ValueError(f"every line must be non-empty text of at most {MAX_CHARS} characters")
    return voice, float(speed), lines


def write_wav(path: Path, samples: np.ndarray, rate: int) -> None:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm.tobytes())


def main() -> int:
    try:
        voice, speed, lines = checked(json.load(sys.stdin))
    except ValueError as error:
        sys.stderr.write(f"invalid request: {error}\n")
        return 2
    out = Path.cwd() / "narration"
    out.mkdir(exist_ok=True)
    kokoro = Kokoro(str(MODEL), str(VOICES))
    durations = []
    for index, line in enumerate(lines):
        samples, rate = kokoro.create(line, voice=voice, speed=speed, lang="en-us")
        if not len(samples):
            sys.stderr.write(f"line {index} produced no audio\n")
            return 1
        write_wav(out / f"{index:02d}.wav", samples, rate)
        durations.append(round(len(samples) / rate, 3))
    (out / "narration.json").write_text(json.dumps({"durations": durations}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
