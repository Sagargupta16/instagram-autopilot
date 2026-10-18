# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["kokoro-onnx==0.6.1"]
# ///
"""Speak each narration line with the local Kokoro voice and write one WAV per line.

Runs in its own locked environment because kokoro-onnx does not support Python 3.14, which the
publisher uses. src/media/narration.py calls it as:
    uv run --frozen --python 3.13 --script scripts/narrate.py REQUEST.json

REQUEST.json holds {"model": path, "voices": path, "voice": name, "speed": number,
"lines": [text, ...], "out": directory}. Each line becomes out/NN.wav (mono, 16-bit, the
model's 24 kHz) and out/narration.json records {"durations": [seconds, ...]} in line order.
Nothing is downloaded here: scripts/fetch_voice_model.py fetches and checks the model files.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np
from kokoro_onnx import Kokoro


def write_wav(path: Path, samples: np.ndarray, rate: int) -> None:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm.tobytes())


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(request["out"])
    out.mkdir(parents=True, exist_ok=True)
    kokoro = Kokoro(request["model"], request["voices"])
    durations = []
    for index, line in enumerate(request["lines"]):
        samples, rate = kokoro.create(
            line, voice=request["voice"], speed=float(request["speed"]), lang="en-us"
        )
        if not len(samples):
            sys.stderr.write(f"line {index} produced no audio\n")
            return 1
        write_wav(out / f"{index:02d}.wav", samples, rate)
        durations.append(round(len(samples) / rate, 3))
    (out / "narration.json").write_text(json.dumps({"durations": durations}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
