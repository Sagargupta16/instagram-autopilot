"""Spoken narration for SVG Reels: the scene's own words, read by a local Kokoro voice.

The script is built only from the validated scene's on-screen text, so the voice never says a
word or number the viewer cannot read on screen (contract 15 already grounds that text). Kokoro
runs in its own locked environment, scripts/narrate.py on Python 3.13, because kokoro-onnx does
not support the publisher's 3.14. Each line opens its beat: the layouts stretch a beat to fit
its line (`Narration.pace`) and the mix starts the line LEAD_S after the beat begins. Any
failure leaves the Reel music-only: narration improves a post, it never skips one. A Reel
the narration would stretch past MAX_S is read again faster (at most MAX_SPEED), so Reels stay
within 15 to 30 seconds where the words allow. This module never reads credentials or
settings, so the sample render runs without them.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "narrate.py"
VOICE_DIR = ROOT / "assets" / "voice"
MODEL = VOICE_DIR / "kokoro-v1.0.fp16.onnx"
VOICES = VOICE_DIR / "voices-v1.0.bin"
PYTHON = "3.13"  # kokoro-onnx 0.6.1 requires Python below 3.14
VOICE = "af_heart"  # the default Kokoro voice; the publisher passes settings.narration_voice
SPEED = 1.0
MAX_S, MAX_SPEED = 30.0, 1.25  # longest Reel the voice should make, and its fastest read
REREADS = 2  # faster reads at most; each one lands closer, since pauses do not speed up
LEAD_S, GAP_S = 0.15, 0.2  # silence before a line inside its beat, and after it
TIMEOUT_S = 600
CREDIT = "Narration: AI-generated voice."
_SUFFIX = re.compile(r"(\d)\s?(k|m|bn|tn)$", re.IGNORECASE)
_SUFFIX_WORDS = {"k": "thousand", "m": "million", "bn": "billion", "tn": "trillion"}
_MONEY = re.compile(r"([$€£¥₹])(\d[\d,]*(?:\.\d+)?(?: (?:thousand|million|billion|trillion))?)")
_CURRENCY = {"$": "dollars", "€": "euros", "£": "pounds", "¥": "yen", "₹": "rupees"}
_YEAR = re.compile(r"(?<![\d.,$€£¥₹])(1[1-9])(\d\d)(?![\d%]|[.,]\d)")
_MONTHS = {
    "Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April", "Jun": "June",
    "Jul": "July", "Aug": "August", "Sep": "September", "Sept": "September", "Oct": "October",
    "Nov": "November", "Dec": "December",
}  # fmt: skip
_MONTH = re.compile(r"\b(" + "|".join(_MONTHS) + r")\.?(?= \d)")

log = logging.getLogger(__name__)


class NarrationError(Exception):
    """Narration could not be made; the Reel goes out with music only."""


@dataclass(frozen=True)
class Narration:
    lines: tuple[str, ...]
    clips: tuple[Path, ...]
    durations: tuple[float, ...]
    speed: float = SPEED

    @property
    def pace(self) -> tuple[float, ...]:
        """Seconds each beat needs so its line ends before the next beat starts."""
        return tuple(round(LEAD_S + seconds + GAP_S, 3) for seconds in self.durations)


def value(text: str) -> str:
    """A stat value as it is said: '1.2m' becomes '1.2 million' and '62%' '62 percent'."""
    text = _SUFFIX.sub(lambda match: f"{match[1]} {_SUFFIX_WORDS[match[2].lower()]}", text)
    return text.replace("%", " percent")


def _year(match: re.Match[str]) -> str:
    """1946 as 'nineteen forty-six', 1900 as 'nineteen hundred', 1905 as 'nineteen oh five'."""
    century, rest = match[1], int(match[2])
    if rest == 0:
        return f"{century} hundred"
    return f"{century} oh {rest}" if rest < 10 else f"{century} {rest}"


def speakable(text: str) -> str:
    """How the voice should read on-screen text; the words and numbers stay the same.

    The voice engine reads "$3.4 billion" as "dollar three point four billion", "1946" as
    "nineteen hundred forty six", "Apr" as "apra" and "CI/CD" as "C I slash C D"; these
    rewrites fix that.
    """
    text = _MONEY.sub(lambda match: f"{match[2]} {_CURRENCY[match[1]]}", text)
    text = _MONTH.sub(lambda match: _MONTHS[match[1]], text)
    text = _YEAR.sub(_year, text)
    return " ".join(text.replace("/", " ").split())


def _stat_body(scene: dict[str, Any]) -> str:
    """The visual's numbers as one line; a chart's unit is said once, not after every value."""
    unit = scene.get("unit")
    if scene["variant"] in {"big_number", "ring"}:
        return f"{value(scene['value'])}{f' {unit}' if unit else ''}, {scene['context']}"
    lead = f"{unit}. " if unit else ""
    if scene["variant"] == "bars":
        return lead + "; ".join(f"{bar['label']}, {value(bar['value'])}" for bar in scene["bars"])
    first, last = scene["points"][0], scene["points"][-1]
    return (
        f"{lead}From {value(first['value'])} in {first['label']} "
        f"to {value(last['value'])} in {last['label']}"
    )


def lines(scene: dict[str, Any]) -> list[str]:
    """One line per beat, from on-screen text only: the hook, each item, the takeaway (a
    myth and its fact are two beats)."""
    if scene["kind"] == "steps":
        body = [f"{step['label']}. {step['detail']}" for step in scene["steps"]]
        return [scene["hook"], *body, scene["takeaway"]]
    if scene["kind"] == "timeline":
        body = [f"{item['date']}. {item['event']}" for item in scene["milestones"]]
        return [scene["hook"], *body, scene["takeaway"]]
    if scene["kind"] == "versus":
        left, right = scene["left"]["name"], scene["right"]["name"]
        body = [f"{r['aspect']}. {left}: {r['left']}. {right}: {r['right']}" for r in scene["rows"]]
        return [scene["hook"], *body, scene["takeaway"]]
    if scene["kind"] == "myths":  # two lines per item, so the strike lands on "Fact"
        body = [
            line for i in scene["items"] for line in (f"Myth: {i['myth']}", f"Fact: {i['fact']}")
        ]
        return [scene["hook"], *body, scene["takeaway"]]
    return [scene["headline"], _stat_body(scene), scene["takeaway"]]


def unavailable() -> str | None:
    """Why narration cannot run here, or None when it can."""
    if missing := [path.name for path in (MODEL, VOICES) if not path.is_file()]:
        return f"voice model missing ({', '.join(missing)}); run scripts/fetch_voice_model.py"
    if shutil.which("uv") is None:
        return "uv is not on PATH"
    return None


def narrate(
    scene: dict[str, Any], workdir: Path, *, voice: str = VOICE, speed: float = SPEED
) -> Narration:
    """Synthesize every line into workdir/narration; NarrationError when anything is off.

    The request goes on stdin and holds no paths: the script reads its model from
    assets/voice and writes into ./narration of the working directory it is given.
    """
    spoken = [speakable(line) for line in lines(scene)]
    out = workdir / "narration"
    request = json.dumps({"voice": voice, "speed": speed, "lines": spoken})
    command = ["uv", "run", "--frozen", "--no-build", "--quiet", "--python", PYTHON]
    command += ["--script", str(SCRIPT)]
    try:
        result = subprocess.run(
            command, input=request, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=workdir
        )
    except subprocess.TimeoutExpired as error:
        raise NarrationError(f"narration timed out after {TIMEOUT_S} seconds") from error
    except OSError as error:
        raise NarrationError("uv could not start") from error
    if result.returncode != 0:
        raise NarrationError(f"narrate.py failed (rc={result.returncode}): {result.stderr[-300:]}")
    try:
        durations = json.loads((out / "narration.json").read_text(encoding="utf-8"))["durations"]
    except (OSError, ValueError, KeyError) as error:
        raise NarrationError("narrate.py wrote no durations") from error
    clips = tuple(out / f"{index:02d}.wav" for index in range(len(spoken)))
    if len(durations) != len(spoken) or not all(clip.is_file() for clip in clips):
        raise NarrationError("narration output does not match its lines")
    seconds = tuple(float(value) for value in durations)
    return Narration(tuple(spoken), clips, seconds, speed)


def for_scene(
    scene: dict[str, Any], workdir: Path, *, voice: str = VOICE, speed: float = SPEED
) -> Narration | None:
    """The narration, or None (logged) so the Reel goes out music-only."""
    if reason := unavailable():
        log.info("SVG Reel without narration: %s", reason)
        return None
    try:
        narration = narrate(scene, workdir, voice=voice, speed=speed)
    except NarrationError as error:
        log.warning("SVG Reel without narration (%s)", error)
        return None
    log.info(
        "Narration ready: %d lines, %.1f s spoken", len(narration.lines), sum(narration.durations)
    )
    return narration


def quicker(narration: Narration, over: float) -> float:
    """The speed that takes `over` seconds off the spoken lines, at most MAX_SPEED."""
    spoken = sum(narration.durations)
    if spoken <= over:
        return MAX_SPEED
    return min(MAX_SPEED, round(narration.speed * spoken / (spoken - over), 2))


def fitted(
    scene: dict[str, Any],
    workdir: Path,
    length: Callable[[tuple[float, ...]], float],
    *,
    voice: str = VOICE,
) -> Narration | None:
    """The narration for a Reel whose length `length(pace)` gives; while that runs past MAX_S
    the lines are read again faster (at most REREADS times, never past MAX_SPEED), and a read
    that fails leaves the last good one."""
    narration = for_scene(scene, workdir, voice=voice)
    for _ in range(REREADS):
        if narration is None or narration.speed >= MAX_SPEED:
            break
        if (over := length(narration.pace) - MAX_S) <= 0:
            break
        speed = quicker(narration, over)
        log.info("Narrated Reel would run %.1f s; reading again at %.2fx", MAX_S + over, speed)
        narration = for_scene(scene, workdir, voice=voice, speed=speed) or narration
        if narration.speed != speed:
            break  # the faster read failed; keep the one that worked
    return narration
